import requests
import json
import os
import time
import argparse
import tkinter as tk
from tkinter import filedialog

API_URL = "http://localhost:8020/v1/chat/completions"
MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct-AWQ"
HEADERS = {"Content-Type": "application/json"}


OUTPUT_TXT_PATH = "D:/alpha_insurance/backend/output.txt"
# Читает содержимое файла с кодом для анализа
def read_input_file(file_path):
   
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"Ошибка: Файл {file_path} не найден.")
        return None
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        return None
 # Отправляет запрос к API для анализа кода.
def send_request_to_api(prompt):
  
    instruction = """Проанализируй следующий код и предоставь структурированный анализ в следующем формате:

1. СЛОЖНОСТЬ:
- Цикломатическая сложность (McCabe)
- Big O нотация
- Общая оценка сложности (Низкая/Средняя/Высокая)

2. ОЦЕНКА КОДА:
- Балл: X/10
- Обоснование оценки

3. ПРОБЛЕМЫ:
- Критические проблемы
- Потенциальные исключения
- Уязвимости безопасности
- Логические ошибки

4. АНТИПАТТЕРНЫ:
- Список обнаруженных антипаттернов
- Краткое описание каждого антипаттерна

5. ПОЛОЖИТЕЛЬНЫЕ МОМЕНТЫ:
- Хорошие практики
- Оптимальные решения
- Правильные паттерны

Пожалуйста, дай структурированный ответ на русском языке. Не переписывай анализируемый код."""

    full_prompt = f"{instruction}\n\n```code\n{prompt}\n```"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": full_prompt}
        ],
       
    }

    try:
        start_time = time.time()
        response = requests.post(API_URL, headers=HEADERS, data=json.dumps(payload))
        response.raise_for_status()
        end_time = time.time()
        print(f"Запрос выполнен за {end_time - start_time:.2f} секунд")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке запроса: {e}")
        return None
# Сохраняет результат анализа в файл.
def save_response(response, output_path):
   
    try:
        if response and "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            # Форматируем ответ для лучшей читаемости
            formatted_content = (
                "АНАЛИЗ КОДА\n"
                "===========\n\n"
                f"{content}"
            )
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(formatted_content)
            print(f"Ответ сохранён в {output_path}")
        else:
            print("Нет ответа для сохранения")
    except Exception as e:
        print(f"Ошибка при сохранении ответа: {e}")
# Открывает диалоговое окно для выбора файла с кодом.
def select_input_file():
    
    root = tk.Tk()
    root.withdraw()  # Скрываем основное окно
    file_path = filedialog.askopenfilename(
        title="Выберите файл с кодом для анализа",
        filetypes=[
            ("Все файлы кода", "*.py;*.cpp;*.c;*.java;*.js;*.cs;*.php;*.rb;*.go"),
            ("Python", "*.py"),
            ("C++", "*.cpp"),
            ("Java", "*.java"),
            ("Все файлы", "*.*")
        ]
    )
    return file_path if file_path else None
#  Обрабатывает аргументы командной строки, организует процесс анализа кода и сохранения результатов.
def main():
   
    parser = argparse.ArgumentParser(description="Анализ кода с помощью AI")
    parser.add_argument("--file", "-f", help="Путь к файлу с кодом для анализа")
    args = parser.parse_args()

    input_file = args.file if args.file else select_input_file()
    if not input_file:
        print("Файл не выбран. Программа завершается.")
        return

    prompt = read_input_file(input_file)
    if prompt is None:
        return

    
    output_dir = os.path.dirname(input_file)
    input_filename = os.path.splitext(os.path.basename(input_file))[0]
    output_file = os.path.join(output_dir, f"{input_filename}_analysis.txt")

    response = send_request_to_api(prompt)
    if response is None:
        return
    
    print("Ответ модели:")
    if "choices" in response and len(response["choices"]) > 0:
        content = response["choices"][0]["message"]["content"]
        print(content)
    else:
        print("Ответ не содержит данных")
    
    save_response(response, output_file)
    print(f"Анализ сохранен в файл: {output_file}")

if __name__ == "__main__":
    main()
