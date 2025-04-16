# Используем официальный образ Python 3.11.9
FROM python:3.11.9-slim

# Устанавливаем необходимые пакеты
RUN apt-get update && apt-get install -y \
    python3-tk \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем папку со шрифтами
COPY fonts/ ./fonts/

# Копируем весь код бэкенда
COPY . .

# Запускаем FastAPI с Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]