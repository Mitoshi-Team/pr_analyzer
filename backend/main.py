from fastapi import FastAPI, Request, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus.flowables import Flowable
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.units import mm, cm
from datetime import datetime, timezone, timedelta
import io
from typing import List, Optional
import os
import base64
import uuid
import json
import textwrap
from pydantic import BaseModel
from parser import GitHubParser

# Определяем московскую временную зону (UTC+3)
MSK_TIMEZONE = timezone(timedelta(hours=3))

def get_moscow_time():
    """Возвращает текущее время в московской временной зоне"""
    return datetime.now(MSK_TIMEZONE)

"""
Задаем шрифт с поддержкой кирилицы
"""
pdfmetrics.registerFont(TTFont('DejaVuSans', 'fonts/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'fonts/DejaVuSans.ttf'))

# Модель данных для отчета
class ReportRequest(BaseModel):
    """
    Модель запроса на создание отчета.
    """
    login: str
    repoLinks: List[str]
    startDate: str
    endDate: str

class ReportResponse(BaseModel):
    """
    Модель ответа с данными отчета.
    """
    id: str
    email: str
    created_at: str
    file_data: str

# Словарь для хранения статусов формирования отчетов
report_status = {}

# Класс запроса на формирование отчета с полем для ID процесса
class ReportStartResponse(BaseModel):
    """
    Модель ответа с ID процесса формирования отчета.
    """
    process_id: str
    message: str

# Класс запроса для проверки статуса отчета
class ReportStatusResponse(BaseModel):
    """
    Модель ответа о статусе формирования отчета.
    """
    process_id: str
    status: str  # "pending", "completed", "failed"
    message: str
    report_id: Optional[str] = None

app = FastAPI(root_path="/api")

# Настройка CORS для Vue.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"http://localhost:{os.getenv('FRONTEND_PORT', '5173')}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Параметры подключения к PostgreSQL из .env
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "alphadb")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "06087083")
DB_PORT = os.getenv("DB_PORT", "5433")

# Строка подключения для asyncpg
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаём асинхронный движок SQLAlchemy
engine = create_async_engine(DATABASE_URL, echo=True)  # echo=True для отладки

# Создаём фабрику сессий
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Папка для хранения отчетов (будет использоваться временно для создания файлов)
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

@app.get("/")
async def read_root():
    """
    Корневой эндпоинт API.
    
    Returns:
        dict: Приветственное сообщение.
    """
    return {"message": "Hello from FastAPI in Docker!"}

@app.post("/check-quality")
async def check_quality(request: Request):
    """
    Проверка качества кода в файлах.
    
    Args:
        request (Request): Запрос с данными файлов.
        
    Returns:
        dict: Результат проверки с сообщением о статусе.
    """
    data = await request.json()
    files = data.get("files", [])
    
    try:
        has_issues = False
        processed_files = []
        
        for file in files:
            filename = file.get("filename")
            content_base64 = file.get("content")
            commit = file.get("commit")
            
            if content_base64:
                try:
                    content = base64.b64decode(content_base64).decode('utf-8')
                    processed_files.append(filename)
                except:
                    has_issues = True
                    return {
                        "status": "error",
                        "message": f"Ошибка декодирования файла {filename}",
                        "result": 1
                    }
        
        return {
            "status": "success" if not has_issues else "failed",
            "message": "Проверка пройдена" if not has_issues else "Найдены проблемы",
            "details": f"Проверены файлы: {', '.join(processed_files)}",
            "result": 0 if not has_issues else 1
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Ошибка проверки",
            "details": str(e),
            "result": 1
        }

"""
    Парсит данные и возвращает страшую структуру с данными
"""
def pars_pr(token, owner, repo, state, start_date=None, end_date=None, author_email=None):
    try:
        parser = GitHubParser(token)

        if not owner or not repo or not state: raise Exception("Missing required parameters: owner, repo, or state")
        return parser.parse_prs(owner, repo, start_date, end_date, author_email)
        
    except Exception as e:
        print('Error:', str(e))

@app.post("/reports/generate")
async def start_report_generation(report_req: ReportRequest, background_tasks: BackgroundTasks):
    """
    Начинает асинхронное формирование отчета в фоновом режиме.
    Возвращает ID процесса формирования, который можно использовать для проверки статуса.
    """
    # Генерируем уникальный ID для процесса формирования отчета
    process_id = str(uuid.uuid4())
    
    # Устанавливаем начальный статус
    report_status[process_id] = {
        "status": "pending",
        "message": "Формирование отчета начато",
        "report_id": None,
        "login": report_req.login
    }
    
    # Запускаем задачу формирования отчета в фоновом режиме
    background_tasks.add_task(
        generate_report_async,
        process_id=process_id,
        report_req=report_req
    )
    
    return ReportStartResponse(
        process_id=process_id,
        message="Формирование отчета начато. Используйте ID процесса для проверки статуса."
    )

@app.get("/reports/status/{process_id}")
async def check_report_status(process_id: str):
    """
    Проверяет статус формирования отчета по ID процесса.
    """
    if process_id not in report_status:
        raise HTTPException(status_code=404, detail=f"Процесс с ID {process_id} не найден")
    
    status_info = report_status[process_id]
    
    return ReportStatusResponse(
        process_id=process_id,
        status=status_info["status"],
        message=status_info["message"],
        report_id=status_info.get("report_id")
    )

async def generate_report_async(process_id: str, report_req: ReportRequest):
    """
    Асинхронная функция для формирования отчета в фоновом режиме.
    Обновляет словарь статусов по завершении.
    """
    try:
        # Запоминаем логин
        login = report_req.login
        
        # Получаем и анализируем данные из репозиториев
        parser = GitHubParser()
        print(f"Начинаем анализ PR для пользователя: {login}")
        print(f"Репозитории: {report_req.repoLinks}")
        print(f"Период: {report_req.startDate} - {report_req.endDate}")
        
        # Обновляем статус
        report_status[process_id]["message"] = "Анализ PR начат"
        
        analysis_results = parser.analyze_all_prs(
            report_req.repoLinks,
            start_date=report_req.startDate,
            end_date=report_req.endDate,
            author_login=login,
            save_to="analysis_report.json"
        )
        
        # Проверяем, получен ли результат анализа
        if not analysis_results:
            print("Предупреждение: анализатор не вернул результаты для PR")
            
        # Обновляем статус
        report_status[process_id]["message"] = "Анализ PR завершен, формирование PDF"
        
        # Создаем буфер для PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                               rightMargin=20*mm, leftMargin=20*mm,
                               topMargin=20*mm, bottomMargin=20*mm)
        
        # [весь код формирования PDF остается без изменений]
        # Создаем стили для текста
        styles = getSampleStyleSheet()
        
        # Модифицируем существующие стили вместо добавления новых с теми же именами
        styles['Title'].fontName = 'DejaVuSans-Bold'
        styles['Title'].fontSize = 16
        styles['Title'].alignment = TA_CENTER
        styles['Title'].spaceAfter = 6*mm
        
        # Модифицируем Heading1 если он существует, иначе добавляем
        if 'Heading1' in styles:
            styles['Heading1'].fontName = 'DejaVuSans-Bold'
            styles['Heading1'].fontSize = 14
            styles['Heading1'].spaceAfter = 3*mm
            styles['Heading1'].spaceBefore = 6*mm
        else:
            styles.add(ParagraphStyle(name='Heading1', 
                                     fontName='DejaVuSans-Bold', 
                                     fontSize=14, 
                                     spaceAfter=3*mm,
                                     spaceBefore=6*mm))
        
        # Модифицируем Heading2 если он существует, иначе добавляем
        if 'Heading2' in styles:
            styles['Heading2'].fontName = 'DejaVuSans-Bold'
            styles['Heading2'].fontSize = 12
            styles['Heading2'].spaceAfter = 2*mm
            styles['Heading2'].spaceBefore = 4*mm
            styles['Heading2'].leftIndent = 5*mm
        else:
            styles.add(ParagraphStyle(name='Heading2', 
                                     fontName='DejaVuSans-Bold', 
                                     fontSize=12, 
                                     spaceAfter=2*mm,
                                     spaceBefore=4*mm,
                                     leftIndent=5*mm))
        
        # Добавляем собственные стили с уникальными именами (не встроенными в ReportLab)
        styles.add(ParagraphStyle(name='NormalText', 
                                 fontName='DejaVuSans', 
                                 fontSize=10,
                                 spaceAfter=1*mm,
                                 textColor=colors.black))
        
        styles.add(ParagraphStyle(name='List', 
                                 fontName='DejaVuSans', 
                                 fontSize=10,
                                 leftIndent=10*mm,
                                 spaceAfter=1*mm))
        
        styles.add(ParagraphStyle(name='SubList', 
                                 fontName='DejaVuSans', 
                                 fontSize=10,
                                 leftIndent=20*mm,
                                 spaceAfter=1*mm))
        
        styles.add(ParagraphStyle(name='StatusOpen', 
                                 fontName='DejaVuSans-Bold', 
                                 fontSize=10,
                                 textColor=colors.blue))
        
        styles.add(ParagraphStyle(name='StatusMerged', 
                                 fontName='DejaVuSans-Bold', 
                                 fontSize=10,
                                 textColor=colors.green))
        
        styles.add(ParagraphStyle(name='StatusRejected', 
                                 fontName='DejaVuSans-Bold', 
                                 fontSize=10,
                                 textColor=colors.red))
        
        # Создаем список элементов документа
        elements = []
        
        # Функция для добавления горизонтальной линии
        class HorizontalLine(Flowable):
            def __init__(self, width, color=colors.black, thickness=1):
                Flowable.__init__(self)
                self.width = width
                self.color = color
                self.thickness = thickness
        
            def draw(self):
                self.canv.setStrokeColor(self.color)
                self.canv.setLineWidth(self.thickness)
                self.canv.line(0, 0, self.width, 0)
        
        # Вспомогательная функция для разбиения длинных строк
        def wrap_text(text, max_width=80):
            return "<br/>".join(textwrap.wrap(text, max_width))
        
        # Функция для получения стиля в зависимости от статуса PR
        def get_status_style(status):
            if status == "open":
                return styles['StatusOpen']
            elif status == "merged":
                return styles['StatusMerged']
            elif status == "rejected":
                return styles['StatusRejected']
            else:
                return styles['NormalText']
        
        # Получаем данные из анализа PR
        analysis_file = os.path.join(os.path.dirname(__file__), "pr_files", "analysis_report_full.json")
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_results = json.load(f)
                print(f"Успешно загружен файл анализа: {analysis_file}")
        except Exception as e:
            print(f"Ошибка при чтении файла анализа: {str(e)}")
            analysis_results = None
        
        # Добавляем титульную страницу
        elements.append(Paragraph(f"Отчет об оценке качества кода", styles['Title']))
        elements.append(Spacer(1, 10*mm))
        elements.append(Paragraph(f"<b>Логин пользователя:</b> {report_req.login}", styles['NormalText']))
        elements.append(Paragraph(f"<b>Период анализа:</b> с {report_req.startDate} по {report_req.endDate}", styles['NormalText']))
        elements.append(Paragraph(f"<b>Дата формирования:</b> {get_moscow_time().strftime('%d.%m.%Y %H:%M:%S (МСК)')}", styles['NormalText']))
        elements.append(Spacer(1, 5*mm))
        
        # Список репозиториев
        elements.append(Paragraph("<b>Репозитории:</b>", styles['NormalText']))
        for repo_link in report_req.repoLinks:
            elements.append(Paragraph(f"- {repo_link}", styles['List']))
        
        elements.append(Spacer(1, 10*mm))
        elements.append(HorizontalLine(450, colors.darkgrey, 2))
        elements.append(PageBreak())
        
        # Определяем содержимое отчета
        if analysis_results and "общий_анализ" in analysis_results:
            общий_анализ = analysis_results["общий_анализ"]
            
            if общий_анализ:
                elements.append(Paragraph("Общий анализ кода", styles['Heading1']))
                elements.append(HorizontalLine(450, colors.grey, 1))
                
                # Общая оценка
                score = общий_анализ.get('overall_score', 'Н/Д')
                score_text = f"<b>Общая оценка кода:</b> {score}"
                elements.append(Paragraph(score_text, styles['NormalText']))
                elements.append(Spacer(1, 5*mm))
                
                # Статистика по статусам PR
                if "pr_status_stats" in общий_анализ:
                    stats = общий_анализ["pr_status_stats"]
                    elements.append(Paragraph("Статистика по PR:", styles['Heading2']))
                    
                    # Создаем таблицу со статистикой
                    data = [
                        ["Открытые:", str(stats.get("open", 0))],
                        ["Принятые:", str(stats.get("merged", 0))],
                        ["Отклоненные:", str(stats.get("rejected", 0))],
                        ["Всего:", str(stats.get("total", 0))]
                    ]
                    
                    # Создание таблицы
                    t = Table(data, colWidths=[100, 80])
                    t.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (0, -1), 'DejaVuSans-Bold'),
                        ('FONTNAME', (1, 0), (1, -1), 'DejaVuSans'),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TEXTCOLOR', (0, 0), (0, 0), colors.blue),  # Открытые - синий
                        ('TEXTCOLOR', (0, 1), (0, 1), colors.green),  # Принятые - зеленый
                        ('TEXTCOLOR', (0, 2), (0, 2), colors.red),  # Отклоненные - красный
                    ]))
                    elements.append(t)
                    elements.append(Spacer(1, 5*mm))
                
                # Повторяющиеся проблемы
                if общий_анализ.get("recurring_issues"):
                    elements.append(Paragraph("Повторяющиеся проблемы:", styles['Heading2']))
                    for issue in общий_анализ["recurring_issues"]:
                        issue_text = wrap_text(f"- {issue['issue']}")
                        elements.append(Paragraph(issue_text, styles['List']))
                    elements.append(Spacer(1, 3*mm))
                
                # Антипаттерны
                if общий_анализ.get("antipatterns"):
                    elements.append(Paragraph("Антипаттерны:", styles['Heading2']))
                    for pattern in общий_анализ["antipatterns"]:
                        pattern_text = wrap_text(f"- {pattern['name']}")
                        elements.append(Paragraph(pattern_text, styles['List']))
            else:
                elements.append(Paragraph("Результаты общего анализа", styles['Heading1']))
                elements.append(HorizontalLine(450, colors.grey, 1))
                elements.append(Paragraph("Результаты общего анализа отсутствуют или неполные", styles['NormalText']))
                elements.append(Paragraph("Возможно, в заданном периоде нет достаточно PR для анализа", styles['NormalText']))
                
            # Детальный анализ PR с разбиением на отдельные страницы
            elements.append(PageBreak())
            elements.append(Paragraph("Детальный анализ Pull Requests", styles['Heading1']))
            elements.append(HorizontalLine(450, colors.grey, 1))
            
            for i, pr in enumerate(analysis_results.get("детальный_анализ", [])):
                # Если не первый PR, добавляем разрыв страницы
                if i > 0:
                    elements.append(PageBreak())
                
                pr_id = pr['pr_info']['id']
                pr_status = pr['pr_info'].get('status', 'open')
                
                # Отображение заголовка PR с его статусом
                status_text = ""
                if pr_status == "open":
                    status_text = " [В РАБОТЕ]"
                elif pr_status == "merged":
                    status_text = " [ПРИНЯТ]"
                elif pr_status == "rejected":
                    status_text = " [ОТКЛОНЕН]"
                
                elements.append(Paragraph(f"PR #{pr_id}{status_text}", styles['Heading2']))
                
                # Основная информация о PR в форме таблицы
                data = [
                    ["Автор:", pr['pr_info']['author']],
                    ["Создан:", pr['pr_info']['created_at']],
                    ["Статус:", pr_status]
                ]
                
                # Добавляем даты закрытия и слияния, если есть
                if pr['pr_info'].get('closed_at'):
                    data.append(["Закрыт:", pr['pr_info']['closed_at']])
                if pr['pr_info'].get('merged_at'):
                    data.append(["Принят:", pr['pr_info']['merged_at']])
                
                data.append(["Репозиторий:", pr['pr_info']['repository']])
                data.append(["Ссылка:", pr['pr_info']['link']])
                
                # Создание таблицы
                t = Table(data, colWidths=[100, 330])
                t.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (0, -1), 'DejaVuSans-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'DejaVuSans'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    # Выделяем статус цветом
                    ('TEXTCOLOR', (1, 2), (1, 2), 
                     colors.blue if pr_status == "open" else
                     colors.green if pr_status == "merged" else
                     colors.red)
                ]))
                elements.append(t)
                elements.append(Spacer(1, 5*mm))
                
                # Данные о сложности и оценке
                if "complexity" in pr:
                    complexity_text = f"<b>Сложность:</b> {pr['complexity']['level']} - {wrap_text(pr['complexity']['explanation'])}"
                    elements.append(Paragraph(complexity_text, styles['NormalText']))
                
                if "code_rating" in pr:
                    rating_text = f"<b>Оценка кода:</b> {pr['code_rating']['score']}/10"
                    elements.append(Paragraph(rating_text, styles['NormalText']))
                    explanation_text = f"<b>Пояснение:</b> {wrap_text(pr['code_rating']['explanation'])}"
                    elements.append(Paragraph(explanation_text, styles['NormalText']))
                
                elements.append(Spacer(1, 3*mm))
                
                # Проблемы
                if pr.get("issues"):
                    elements.append(Paragraph("Проблемы:", styles['Heading2']))
                    for issue in pr["issues"]:
                        issue_text = wrap_text(f"- [{issue['type']}] {issue['description']}")
                        elements.append(Paragraph(issue_text, styles['List']))
                    elements.append(Spacer(1, 3*mm))
                
                # Антипаттерны
                if pr.get("antipatterns"):
                    elements.append(Paragraph("Антипаттерны:", styles['Heading2']))
                    for pattern in pr["antipatterns"]:
                        if isinstance(pattern, dict) and "name" in pattern:
                            pattern_text = wrap_text(f"- {pattern['name']}")
                        else:
                            pattern_text = wrap_text(f"- {pattern}")
                        elements.append(Paragraph(pattern_text, styles['List']))
                    elements.append(Spacer(1, 3*mm))
                
                # Положительные моменты
                if pr.get("positive_aspects"):
                    elements.append(Paragraph("Положительные моменты:", styles['Heading2']))
                    for pos in pr["positive_aspects"]:
                        if isinstance(pos, dict) and "description" in pos:
                            pos_text = wrap_text(f"- {pos['description']}")
                        else:
                            pos_text = wrap_text(f"- {pos}")
                        elements.append(Paragraph(pos_text, styles['List']))
                    elements.append(Spacer(1, 3*mm))
                
                # Коммиты
                if pr['pr_info'].get('commits'):
                    elements.append(Paragraph("Коммиты:", styles['Heading2']))
                    for commit in pr['pr_info']['commits']:
                        commit_text = wrap_text(f"- {commit['message']} ({commit['sha'][:7]})")
                        elements.append(Paragraph(commit_text, styles['List']))
                
                # Разделитель между PR
                elements.append(Spacer(1, 5*mm))
                elements.append(HorizontalLine(450, colors.lightgrey, 1))
        else:
            elements.append(Paragraph("Данные анализа не найдены", styles['Heading1']))
            elements.append(HorizontalLine(450, colors.grey, 1))
            elements.append(Paragraph("Возможные причины:", styles['Heading2']))
            elements.append(Paragraph("- Файл анализа не существует или поврежден", styles['List']))
            elements.append(Paragraph("- Нет PR в указанном периоде", styles['List']))
            elements.append(Paragraph("- PR не принадлежат указанному пользователю", styles['List']))
            elements.append(Paragraph(f"Проверьте логин пользователя: {report_req.login}", styles['NormalText']))
        
        # Сборка документа
        doc.build(elements)
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        
        # Сохраняем отчет в базу данных
        try:
            # Генерируем целочисленный id
            current_time = int(datetime.now().timestamp())
            report_id = abs(hash(f"{current_time}{login}")) % (2**31)
            
            async with async_session() as session:
                # Проверяем существование таблицы
                table_check = await session.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        AND table_name = 'code_review_reports'
                    )
                """))
                table_exists = table_check.scalar()
                
                if not table_exists:
                    print("Таблица code_review_reports не существует, создаем...")
                    await session.execute(text("""
                        CREATE TABLE IF NOT EXISTS code_review_reports (
                            id BIGINT PRIMARY KEY,
                            email VARCHAR(255) NOT NULL,
                            creation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            file_data BYTEA NOT NULL
                        )
                    """))
                    await session.commit()
                    print("Таблица code_review_reports создана успешно")
                
                # Сохраняем отчет
                print(f"Сохраняем отчет в БД для логина: {login}, ID: {report_id}")
                try:
                    result = await session.execute(text("""
                        INSERT INTO code_review_reports (id, email, file_data, creation_date)
                        VALUES (:id, :email, :file_data, CURRENT_TIMESTAMP + INTERVAL '3 hours')
                        RETURNING id
                    """), {
                        "id": report_id,
                        "email": login,
                        "file_data": pdf_data
                    })
                    inserted_id = result.scalar()
                    await session.commit()
                    print(f"Отчет успешно сохранен в БД с ID: {inserted_id}")
                    
                    # Обновляем статус на успешный
                    report_status[process_id]["status"] = "completed"
                    report_status[process_id]["message"] = "Отчет успешно сформирован и сохранен"
                    report_status[process_id]["report_id"] = str(report_id)
                    
                except Exception as insert_error:
                    print(f"Ошибка при вставке записи в БД: {str(insert_error)}")
                    await session.rollback()
                    
                    # Обновляем статус на ошибку
                    report_status[process_id]["status"] = "failed"
                    report_status[process_id]["message"] = f"Ошибка при сохранении в БД: {str(insert_error)}"
                    raise insert_error
                    
        except Exception as db_error:
            print(f"Ошибка при сохранении отчета в БД: {str(db_error)}")
            report_status[process_id]["status"] = "failed"
            report_status[process_id]["message"] = f"Ошибка при работе с БД: {str(db_error)}"
            # Сохраняем ID отчета, если он был создан
            if "report_id" in locals():
                report_status[process_id]["report_id"] = str(report_id)
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Ошибка при создании отчета: {str(e)}")
        print(f"Детали ошибки: {error_details}")
        
        # Обновляем статус на ошибку
        report_status[process_id]["status"] = "failed"
        report_status[process_id]["message"] = f"Ошибка при формировании отчета: {str(e)}"

@app.get("/test-db")
async def test_db():
    """
    Тестирование соединения с базой данных.
    
    Returns:
        dict: Статус подключения к БД.
    """
    try:
        async with async_session() as session:
            # Выполняем тестовый запрос
            result = await session.execute(text("SELECT 1 AS test"))
            row = result.fetchone()
        return {"db_status": "Connected", "result": row[0] if row else None}
    except Exception as e:
        return {"db_status": "Error", "error": str(e)}

@app.get("/tables")
async def get_tables():
    """
    Получение списка всех таблиц в базе данных.
    
    Returns:
        dict: Список таблиц или сообщение об ошибке.
    """
    try:
        async with async_session() as session:
            # SQL запрос для получения списка всех таблиц
            query = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            result = await session.execute(query)
            tables = [row[0] for row in result.fetchall()]
            return {"tables": tables}
    except Exception as e:
        return {"error": str(e)}

# Эндпоинты для работы с отчетами

@app.get("/reports")
async def get_reports():
    """
    Получение списка всех отчетов.
    """
    try:
        async with async_session() as session:
            # Проверяем существование таблицы
            table_check = await session.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_name = 'code_review_reports'
                )
            """))
            table_exists = table_check.scalar()
            
            if not table_exists:
                print("Таблица code_review_reports не существует при запросе отчетов")
                return []
            
            # Получаем данные с сохранением полного формата времени и даты
            result = await session.execute(text("""
                SELECT id, email, creation_date
                FROM code_review_reports
                ORDER BY creation_date DESC
            """))
            
            reports = []
            for row in result:
                # Сохраняем полный формат timestamp с часовым поясом
                if row[2]:
                    creation_date = row[2].isoformat()
                    print(f"Отчет ID: {row[0]}, время создания: {creation_date}")
                else:
                    creation_date = None
                    
                reports.append({
                    "id": row[0],
                    "email": row[1],
                    "created_at": creation_date
                })
            
            print(f"Получено отчетов: {len(reports)}")
            return reports
    except Exception as e:
        print(f"Ошибка при получении списка отчетов: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении списка отчетов: {str(e)}")

@app.get("/reports/{report_id}/download")
async def download_report(report_id: str):
    """
    Скачивание отчета по ID.
    
    Args:
        report_id (str): Идентификатор отчета.
        
    Returns:
        StreamingResponse: PDF файл отчета для скачивания.
        
    Raises:
        HTTPException: Если отчет не найден или произошла ошибка при скачивании.
    """
    try:
        # Преобразуем строковый ID в целое число
        report_id_int = int(report_id)
        
        async with async_session() as session:
            result = await session.execute(text("""
                SELECT file_data, email FROM code_review_reports WHERE id = :report_id
            """), {"report_id": report_id_int})
            
            row = result.first()
            if not row:
                raise HTTPException(status_code=404, detail="Отчет не найден")
                
            file_data = row[0]
            email = row[1]
            
            # Возвращаем PDF напрямую через StreamingResponse
            return StreamingResponse(
                io.BytesIO(file_data),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=report_{email}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                }
            )
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный формат ID отчета")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при скачивании отчета: {str(e)}")

@app.on_event("shutdown")
async def shutdown():
    """
    Обработчик события завершения работы приложения.
    Освобождает ресурсы подключения к БД.
    """
    await engine.dispose()