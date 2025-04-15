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
    email: str
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
def pars_pr(token, owner, repo, state):
    try:
        parser = GitHubParser(token)

        if not owner or not repo or not state: raise Exception("Missing required parameters: owner, repo, or state")
        return parser.parse_prs(owner, repo, state)
        
    except Exception as e:
        print('Error:', str(e))


@app.get("/reports/generate")
async def generate_report():
    # Пример данных
    data = {
        "Общая оценка кода": 7.5,
        "Повторяющиеся проблемы": [
            "Недостаток комментариев",
            "Слабое покрытие тестами",
            "Нарушение соглашений об именовании"
        ],
        "Антипаттерны": [
            "God Object",
            "Copy-Paste Programming"
        ],
        "PRs": [
            {
                "Ссылка на PR": "https://github.com/example/repo/pull/101",
                "Описание PR": "Добавлен функционал экспорта данных в CSV",
                "Оценка сложности кода": "M",
                "Оценка кода": 6,
                "Список проблем": [
                    "Недостаточно покрыт unit-тестами",
                    "Смешение логики и представления"
                ],
                "Антипаттерны": [
                    "Spaghetti Code"
                ],
                "Положительные моменты": [
                    "Хорошая читаемость кода",
                    "Соответствие стилю проекта"
                ]
            },
            {
                "Ссылка на PR": "https://github.com/example/repo/pull/102",
                "Описание PR": "Рефакторинг модуля авторизации",
                "Оценка сложности кода": "L",
                "Оценка кода": 8,
                "Список проблем": [
                    "Слишком длинные функции"
                ],
                "Антипаттерны": [
                    "Long Method"
                ],
                "Положительные моменты": [
                    "Выделены интерфейсы",
                    "Улучшена структура классов"
                ]
            }
        ]
    }

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

    # Генерация отчета
    write_line("Отчет об оценке качества кода", 0)
    write_line(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    write_line("")
    write_line(f"Общая оценка кода: {data['Общая оценка кода']}")
    write_line("Повторяющиеся проблемы:")
    for problem in data["Повторяющиеся проблемы"]:
        write_line(f"- {problem}", 1)

    write_line("Антипаттерны:")
    for pattern in data["Антипаттерны"]:
        write_line(f"- {pattern}", 1)

    write_line("")
    write_line("Анализ Pull Requests:")
    for pr in data["PRs"]:
        write_line(f"Ссылка на PR: {pr['Ссылка на PR']}", 1)
        write_line(f"Описание PR: {pr['Описание PR']}", 1)
        write_line(f"Оценка сложности: {pr['Оценка сложности кода']}", 1)
        write_line(f"Оценка кода: {pr['Оценка кода']}", 1)

        write_line("Проблемы:", 1)
        for p in pr["Список проблем"]:
            write_line(f"- {p}", 2)

        write_line("Антипаттерны:", 1)
        for a in pr["Антипаттерны"]:
            write_line(f"- {a}", 2)

        write_line("Положительные моменты:", 1)
        for pos in pr["Положительные моменты"]:
            write_line(f"- {pos}", 2)
        write_line("")

    c.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=code_report.pdf"
        }
    )


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

# @app.post("/reports/generate")
# async def generate_report(report_req: ReportRequest):
#     """
#     Генерация отчета о проверке кода.
    
#     Args:
#         report_req (ReportRequest): Запрос на создание отчета с email и датами.
        
#     Returns:
#         dict: Статус создания отчета и ID отчета.
        
#     Raises:
#         HTTPException: Если произошла ошибка при создании отчета.
#     """
#     try:
#         report_id = str(uuid.uuid4())
        
#         # Создаем содержимое отчета
#         report_content = f"Отчет для: {report_req.email}\n"
#         report_content += f"Период: с {report_req.startDate} по {report_req.endDate}\n"
#         report_content += f"Создан: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
#         report_content += "Это демонстрационный отчет о проверке кода.\n"
#         report_content += "Здесь будут результаты анализа PR за указанный период.\n"
        
#         # Сохраняем информацию об отчете в БД
#         async with async_session() as session:
#             await session.execute(text("""
#                 INSERT INTO code_review_reports (id, email, creation_date, file_data)
#                 VALUES (:id, :email, CURRENT_TIMESTAMP, :file_data)
#             """), {
#                 "id": report_id,
#                 "email": report_req.email,
#                 "file_data": report_content
#             })
#             await session.commit()
            
#         return {"success": True, "report_id": report_id}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Ошибка при создании отчета: {str(e)}")

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
        FileResponse: Файл отчета для скачивания.
        
    Raises:
        HTTPException: Если отчет не найден или произошла ошибка при скачивании.
    """
    try:
        async with async_session() as session:
            result = await session.execute(text("""
                SELECT file_data, email FROM code_review_reports WHERE id = :report_id
            """), {"report_id": report_id})
            
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Отчет не найден")
                
            file_data = row[0]
            email = row[1]
            
            # Создаем временный файл для скачивания
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            file_name = f"report_{email}_{timestamp}.txt"
            file_path = os.path.join(REPORTS_DIR, file_name)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_data)
                
            return FileResponse(
                path=file_path, 
                filename=file_name,
                media_type='text/plain',
                background=FileResponse.BackgroundTask(lambda: os.remove(file_path) if os.path.exists(file_path) else None)
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