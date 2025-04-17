from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from fastapi.responses import StreamingResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from datetime import datetime
import io
from typing import List, Optional
from datetime import datetime
import os
import base64
import uuid
import json
from pydantic import BaseModel
from parser import GitHubParser

"""
Задаем шрифт с поддержкой кирилицы
"""
pdfmetrics.registerFont(TTFont('DejaVuSans', 'fonts/DejaVuSans.ttf'))

# Модель данных для отчета
class ReportRequest(BaseModel):
    """
    Модель запроса на создание отчета.
    """
    email: str  # Оставляем для обратной совместимости
    login: Optional[str] = None
    repoLinks: Optional[List[str]] = None
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
async def generate_report(report_req: ReportRequest):
    try:
        # Получаем логин пользователя из запроса или используем email
        login = report_req.login or report_req.email
        
        # Если переданы ссылки на репозитории, запускаем анализ
        if report_req.repoLinks:
            try:
                # Создаем парсер GitHub
                parser = GitHubParser()
                
                # Запускаем анализ всех PR
                analysis_results = parser.analyze_all_prs(
                    repo_links=report_req.repoLinks,
                    start_date=report_req.startDate,
                    end_date=report_req.endDate,
                    author_login=login,
                    save_to="analysis_report.json"
                )
                
                if not analysis_results:
                    print(f"Предупреждение: Не найдены PR для анализа для пользователя {login}")
            except Exception as e:
                print(f"Ошибка при анализе репозиториев: {str(e)}")
        
        # Создаем буфер для PDF
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        c.setFont('DejaVuSans', 12)
        width, height = A4

        y = height - 50
        line_height = 15

        def write_line(text, indent=0):
            nonlocal y
            c.drawString(50 + indent * 20, y, text)
            y -= line_height
            if y < 50:
                c.showPage()
                c.setFont('DejaVuSans', 12)
                y = height - 50

        # Получаем данные из анализа PR
        analysis_file = os.path.join(os.path.dirname(__file__), "pr_files", "analysis_report_full.json")
        try:
            with open(analysis_file, 'r', encoding='utf-8') as f:
                analysis_results = json.load(f)
        except Exception as e:
            print(f"Ошибка при чтении файла анализа: {str(e)}")
            analysis_results = None

        # Генерация отчета
        write_line(f"Отчет об оценке качества кода для {login}")
        write_line(f"Период: с {report_req.startDate} по {report_req.endDate}")
        
        # Добавим информацию о репозиториях
        if report_req.repoLinks:
            write_line("Проанализированные репозитории:")
            for link in report_req.repoLinks:
                write_line(f"- {link}", 1)
                
        write_line(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        write_line("")

        if analysis_results and "общий_анализ" in analysis_results:
            общий_анализ = analysis_results["общий_анализ"]
            
            write_line(f"Общая оценка кода: {общий_анализ.get('overall_score', 'Н/Д')}")
            
            if общий_анализ.get("recurring_issues"):
                write_line("")
                write_line("Повторяющиеся проблемы:")
                for issue in общий_анализ["recurring_issues"]:
                    write_line(f"- {issue['issue']}", 1)

            if общий_анализ.get("antipatterns"):
                write_line("")
                write_line("Антипаттерны:")
                for pattern in общий_анализ["antipatterns"]:
                    write_line(f"- {pattern['name']}", 1)

            write_line("")
            write_line("Детальный анализ Pull Requests:")
            
            for pr in analysis_results.get("детальный_анализ", []):
                write_line("")
                write_line(f"PR #{pr['pr_info']['id']}", 1)
                write_line(f"Автор: {pr['pr_info']['author']}", 1)
                write_line(f"Создан: {pr['pr_info']['created_at']}", 1)
                write_line(f"Ссылка: {pr['pr_info']['link']}", 1)
                
                if "complexity" in pr:
                    write_line(f"Сложность: {pr['complexity']['level']} - {pr['complexity']['explanation']}", 1)
                
                if "code_rating" in pr:
                    write_line(f"Оценка кода: {pr['code_rating']['score']}/10", 1)
                    write_line(f"Пояснение: {pr['code_rating']['explanation']}", 1)

                if pr.get("issues"):
                    write_line("Проблемы:", 1)
                    for issue in pr["issues"]:
                        write_line(f"- [{issue['type']}] {issue['description']}", 2)

                if pr.get("antipatterns"):
                    write_line("Антипаттерны:", 1)
                    for pattern in pr["antipatterns"]:
                        write_line(f"- {pattern['name']}", 2)

                if pr.get("positive_aspects"):
                    write_line("Положительные моменты:", 1)
                    for pos in pr["positive_aspects"]:
                        write_line(f"- {pos}", 2)

                if pr['pr_info'].get('commits'):
                    write_line("Коммиты:", 1)
                    for commit in pr['pr_info']['commits']:
                        write_line(f"- {commit['message']} ({commit['sha'][:7]})", 2)
                
                write_line("") # Пустая строка между PR
        else:
            write_line("Данные анализа не найдены")
            write_line("Возможные причины:")
            write_line("- Файл анализа не существует или поврежден", 1)
            write_line("- Нет PR в указанном периоде", 1)
            write_line("- PR не принадлежат указанному автору", 1)

        c.save()
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        
        # Генерируем целочисленный id
        current_time = int(datetime.now().timestamp())
        report_id = abs(hash(f"{current_time}{report_req.email}")) % (2**31)
        
        try:
            async with async_session() as session:
                await session.execute(text("""
                    INSERT INTO code_review_reports (id, email, creation_date, file_data)
                    VALUES (:id, :email, CURRENT_TIMESTAMP, :file_data)
                """), {
                    "id": report_id,
                    "email": report_req.email,
                    "file_data": pdf_data
                })
                await session.commit()
        except Exception as db_error:
            print(f"Предупреждение: не удалось сохранить отчет в БД: {str(db_error)}")
        
        # Возвращаем PDF как ответ
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=report_{report_req.email.replace('@', '_')}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании отчета: {str(e)}")


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
    
    Returns:
        list: Список всех отчетов в системе.
        
    Raises:
        HTTPException: Если произошла ошибка при получении списка отчетов.
    """
    try:
        async with async_session() as session:
            result = await session.execute(text("""
                SELECT id, email, creation_date, file_data
                FROM code_review_reports
                ORDER BY creation_date DESC
            """))
            
            reports = []
            for row in result:
                reports.append({
                    "id": row[0],
                    "email": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "file_data": row[3]
                })
            
            return reports
    except Exception as e:
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
        async with async_session() as session:
            result = await session.execute(text("""
                SELECT file_data, email FROM code_review_reports WHERE id = :report_id
            """), {"report_id": report_id})
            
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