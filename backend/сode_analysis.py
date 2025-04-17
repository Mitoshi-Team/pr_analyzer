import requests
import json
import os
import time
import argparse
import tkinter as tk
from tkinter import filedialog

# Исправляем URL для обращения к API на правильный порт из docker-compose
API_URL = "http://vllm:8000/v1/chat/completions"  # внутри контейнера используем сетевое имя

MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct-AWQ"
HEADERS = {"Content-Type": "application/json"}

# Максимальное количество попыток отправки запроса
MAX_RETRIES = 3
# Время ожидания между попытками (в секундах)
RETRY_DELAY = 2

# Читает содержимое файла с кодом для анализа
def __read_input_file(file_path):
   
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
    instruction = """Проанализируй следующий код или данные и предоставь анализ в JSON формате:
{
    "complexity": {
        "level": "S|M|L",
        "explanation": "Объяснение оценки сложности"
    },
    "code_rating": {
        "score": 0-10,
        "explanation": "Обоснование оценки"
    },
    "issues": [
        {
            "type": "критическая|предупреждение|информация",
            "description": "Описание проблемы"
        }
    ],
    "antipatterns": [
        {
            "name": "Название антипаттерна"
        }
    ],
    "positive_aspects": [
        "Описание положительного аспекта"
    ]
}"""

    # Ограничиваем размер промпта, чтобы избежать превышения токенов (приблизительно)
    max_prompt_chars = 20000  # Примерное ограничение на символы для безопасности
    if len(prompt) > max_prompt_chars:
        print(f"Предупреждение: запрос слишком длинный ({len(prompt)} символов), сокращаем до {max_prompt_chars}")
        prompt = prompt[:max_prompt_chars] + "\n...[контент обрезан из-за превышения максимальной длины]"

    full_prompt = f"{instruction}\n\n```code\n{prompt}\n```"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": full_prompt}
        ]
    }

    # Используем повторные попытки при ошибках подключения
    retries = 0
    while retries < MAX_RETRIES:
        try:
            start_time = time.time()
            print(f"Отправка запроса к API ({retries+1}/{MAX_RETRIES})...")
            response = requests.post(API_URL, headers=HEADERS, data=json.dumps(payload), timeout=120)
            response.raise_for_status()
            end_time = time.time()
            print(f"Запрос выполнен за {end_time - start_time:.2f} секунд")
            return response.json()
        except requests.exceptions.ConnectionError as e:
            retries += 1
            print(f"Ошибка подключения ({retries}/{MAX_RETRIES}): {e}")
            if retries < MAX_RETRIES:
                print(f"Повторная попытка через {RETRY_DELAY} сек...")
                time.sleep(RETRY_DELAY)
            else:
                print("Все попытки подключения исчерпаны.")
                # Возвращаем пустой результат вместо None, чтобы не вызывать ошибки при обработке
                return {"choices": [{"message": {"content": "{}"}}]}
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при отправке запроса: {e}")
            # Возвращаем пустой результат вместо None
            return {"choices": [{"message": {"content": "{}"}}]}

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
def __save_response(response, output_path):
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
def __select_input_file():
    
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

    input_file = args.file if args.file else __select_input_file()
    if not input_file:
        print("Файл не выбран. Программа завершается.")
        return

    prompt = __read_input_file(input_file)
    if prompt is None:
        return

    
    output_dir = os.path.dirname(input_file)
    input_filename = os.path.splitext(os.path.basename(input_file))[0]
    output_file = os.path.join(output_dir, f"{input_filename}_analysis.txt")

    response = send_request_to_api(prompt)
    if response is None:
        return
    
    analysis = __save_response(response, output_file)
    if analysis:
        print("\nРезультаты анализа:")
        print(f"Сложность: {analysis.get('сложность', {}).get('уровень')}")
        print(f"Оценка кода: {analysis.get('оценка_кода', {}).get('балл')}/10")
        print(f"Количество найденных проблем: {len(analysis.get('проблемы', []))}")
        print(f"Количество антипаттернов: {len(analysis.get('антипаттерны', []))}")
        print(f"Количество положительных аспектов: {len(analysis.get('положительные_аспекты', []))}")
    
    print(f"\nПолный анализ сохранен в файл: {output_file}")

if __name__ == "__main__":
    main()
