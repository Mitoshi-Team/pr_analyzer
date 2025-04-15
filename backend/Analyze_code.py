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
    instruction = """Проанализируй следующий код и предоставь анализ в JSON формате:
{
    "complexity": {
        "level": "S|M|L",
        "explanation": "Объяснение оценки сложности"
    },
    "codeScore": {
        "score": 0-10,
        "explanation": "Обоснование оценки"
    },
    "issues": [
        {
            "type": "critical|warning|info",
            "description": "Описание проблемы"
        }
    ],
    "antipatterns": [
        {
            "name": "Название антипаттерна",
            "description": "Описание антипаттерна"
        }
    ],
    "positiveAspects": [
        "Описание положительного аспекта"
    ]
}"""

    full_prompt = f"{instruction}\n\n```code\n{prompt}\n```"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": full_prompt}
        ]
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

def parse_analysis(content):
    try:
        # Находим JSON в тексте ответа
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = content[json_start:json_end]
            return json.loads(json_str)
        return None
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON: {e}")
        return None

# Сохраняет результат анализа в файл.
def save_response(response, output_path):
    try:
        if response and "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            analysis = parse_analysis(content)
            
            if analysis:
                formatted_content = json.dumps(analysis, indent=2, ensure_ascii=False)
            else:
                formatted_content = content

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(formatted_content)
            print(f"Ответ сохранён в {output_path}")
            return analysis
        else:
            print("Нет ответа для сохранения")
            return None
    except Exception as e:
        print(f"Ошибка при сохранении ответа: {e}")
        return None

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
    
    analysis = save_response(response, output_file)
    if analysis:
        print("\nРезультаты анализа:")
        print(f"Сложность: {analysis.get('complexity', {}).get('level')}")
        print(f"Оценка кода: {analysis.get('codeScore', {}).get('score')}/10")
        print(f"Количество найденных проблем: {len(analysis.get('issues', []))}")
        print(f"Количество антипаттернов: {len(analysis.get('antipatterns', []))}")
        print(f"Количество положительных аспектов: {len(analysis.get('positiveAspects', []))}")
    
    print(f"\nПолный анализ сохранен в файл: {output_file}")

if __name__ == "__main__":
    main()
