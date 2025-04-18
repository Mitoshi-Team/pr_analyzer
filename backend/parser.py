import requests
from datetime import datetime
import json
import sys
from сode_analysis import send_request_to_api, parse_analysis
import os
import re
import time
from dotenv import load_dotenv

try:
    from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
except ImportError:
    print("Warning: tenacity library not installed. Falling back to basic retry logic.")
    retry = lambda *args, **kwargs: lambda x: x  # Заглушка для декоратора
    stop_after_attempt = lambda x: None
    wait_fixed = lambda x: None
    retry_if_exception_type = lambda x: None

# Загружаем переменные окружения из файла .env
load_dotenv()

# Настройка повторных попыток для запросов API
MAX_ANALYSIS_RETRIES = 3
RETRY_INTERVAL = 5  # секунд


class GitHubParser:
    def __init__(self, token=None):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        # Используем токен из переменных окружения, если не передан явно
        if token is None:
            token = os.getenv("GITHUB_TOKEN")
        if token:
            self.headers["Authorization"] = f"token {token}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(5),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.HTTPError)),
        reraise=True
    )
    def get_pr_list(self, owner, repo, state="open", author_login=None):
        """
        Получение списка pull request'ов из репозитория с поддержкой пагинации и фильтрации по автору.
        
        Args:
            owner (str): Владелец репозитория.
            repo (str): Название репозитория.
            state (str, optional): Состояние PR (open/closed/all). По умолчанию "open".
            author_login (str, optional): Логин автора PR для фильтрации. По умолчанию None (все авторы).
            
        Returns:
            list: Список pull request'ов.
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP.
            Exception: При других ошибках.
        """
        try:
            all_prs = []
            page = 1
            per_page = 100  # Максимальное количество результатов на странице
            
            if author_login:
                # Используем Search API для фильтрации по автору
                query = f"type:pr repo:{owner}/{repo} author:{author_login}"
                if state != "all":
                    query += f" state:{state}"
                url = f"https://api.github.com/search/issues?q={query}&page={page}&per_page={per_page}"
            else:
                # Стандартный запрос для получения всех PR
                url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state={state}&page={page}&per_page={per_page}"

            while True:
                print(f"Запрашиваем PR: страница {page}, {owner}/{repo}, состояние: {state}" + (f", автор: {author_login}" if author_login else ""))
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                
                if author_login:
                    # Для Search API данные находятся в поле "items"
                    page_results = response.json().get("items", [])
                else:
                    page_results = response.json()
                    
                if not page_results:  # Если страница пустая, значит PR больше нет
                    break
                    
                all_prs.extend(page_results)
                print(f"Получено {len(page_results)} PR на странице {page}, всего: {len(all_prs)}")
                
                # Проверяем, есть ли следующая страница
                if len(page_results) < per_page:
                    break
                    
                page += 1
                # Обновляем URL для следующей страницы
                if author_login:
                    url = f"https://api.github.com/search/issues?q={query}&page={page}&per_page={per_page}"
                else:
                    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state={state}&page={page}&per_page={per_page}"
                
                time.sleep(1)  # Задержка для избежания лимитов API
                
            return all_prs
        except requests.exceptions.HTTPError as e:
            if response.status_code == 403:
                print("Превышен лимит запросов к API GitHub. Используйте токен или подождите перед повторной попыткой.")
            elif response.status_code == 404:
                print(f"Репозиторий {owner}/{repo} не найден или доступ ограничен.")
            else:
                print(f"Ошибка HTTP при запросе PR: {e}")
            raise e
        except Exception as e:
            print(f"Ошибка при получении списка PR: {e}")
            raise e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(5),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.HTTPError)),
        reraise=True
    )
    def get_pr_diff(self, owner, repo, pr_number):
        """
        Получение diff-файла для конкретного pull request'а.
        
        Args:
            owner (str): Владелец репозитория.
            repo (str): Название репозитория.
            pr_number (int): Номер pull request'а.
            
        Returns:
            str: Текст diff-файла.
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP.
            Exception: При других ошибках.
        """
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
            diff_headers = self.headers.copy()
            diff_headers["Accept"] = "application/vnd.github.v3.diff"
            response = requests.get(url, headers=diff_headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            if response.status_code == 403:
                print("Rate limit exceeded for diff request. Consider using a GitHub token.")
            raise e
        except Exception as e:
            print(f"Error fetching PR diff #{pr_number}: {e}")
            raise e

    def format_code_from_diff(self, diff):
        """
        Извлечение кода из diff-файла.
        
        Args:
            diff (str): Текст diff-файла.
            
        Returns:
            str: Форматированный код с удалёнными строками diff-маркировки.
        """
        lines = diff.splitlines()
        code = []
        for line in lines:
            if line.startswith('+') and not line.startswith('+++'):
                code.append(line[1:])
            elif line.startswith('-') and not line.startswith('---'):
                continue
            else:
                code.append(line)
        return "\n".join(code)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(5),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.HTTPError)),
        reraise=True
    )
    def get_pr_commits(self, owner, repo, pr_number):
        """Получает информацию о коммитах PR с повторными попытками при сетевых ошибках."""
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/commits"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return [{"sha": commit["sha"], 
                    "message": commit["commit"]["message"],
                    "author": commit["commit"]["author"]["name"]} 
                   for commit in response.json()]
        except Exception as e:
            print(f"Error fetching commits for PR #{pr_number}: {e}")
            return []

    def parse_prs(self, owner, repo, start_date=None, end_date=None, author_login=None, save_to="pr_data.json"):
        """
        Получение и анализ pull request'ов из репозитория за указанный период времени для указанного автора.
        Включает как принятые, так и отклоненные PR.
        
        Args:
            owner (str): Владелец репозитория.
            repo (str): Название репозитория.
            start_date (str, optional): Начальная дата периода в формате "YYYY-MM-DD". По умолчанию None (без ограничения).
            end_date (str, optional): Конечная дата периода в формате "YYYY-MM-DD". По умолчанию None (без ограничения).
            author_login (str, optional): Логин автора PR для фильтрации. По умолчанию None (все авторы).
            save_to (str, optional): Путь для сохранения данных. По умолчанию "pr_data.json".
            
        Returns:
            list: Список словарей с данными о pull request'ах.
        """
        # Создаем директорию для анализов если её нет
        analysis_dir = os.path.join(os.path.dirname(__file__), "pr_files")
        os.makedirs(analysis_dir, exist_ok=True)
        
        # Конвертируем строковые даты в объекты datetime для сравнения
        start_datetime = None
        end_datetime = None
        
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                print(f"Неверный формат начальной даты: {start_date}. Используйте формат YYYY-MM-DD.")
        
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
                # Устанавливаем время на конец дня
                end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            except ValueError:
                print(f"Неверный формат конечной даты: {end_date}. Используйте формат YYYY-MM-DD.")
        
        # Получаем все PR (включая открытые, закрытые и объединенные)
        pr_list = self.get_pr_list(owner, repo, state="all", author_login=author_login)
        
        if not pr_list:
            print(f"Предупреждение: PR не найдены для репозитория {owner}/{repo}" + (f" с автором {author_login}" if author_login else ""))
            return []
        
        parsed_data = []

        for pr in pr_list:
            pr_number = pr["number"]
            print(f"Обработка PR #{pr_number} от {pr['created_at']} (автор: {pr['user']['login']})")
            
            # Проверяем, соответствует ли PR заданному периоду времени
            pr_created_at = datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            
            # Фильтрация по дате
            if start_datetime and pr_created_at < start_datetime:
                print(f"PR #{pr_number} пропущен: дата создания ({pr_created_at}) раньше {start_datetime}")
                continue
            if end_datetime and pr_created_at > end_datetime:
                print(f"PR #{pr_number} пропущен: дата создания ({pr_created_at}) позже {end_datetime}")
                continue
            
            # Определяем статус PR
            pr_status = "open"
            if pr.get("closed_at"):
                if pr.get("merged_at"):
                    pr_status = "merged"
                else:
                    pr_status = "rejected"  # PR был закрыт, но не объединен - отклонен
            
            try:
                diff = self.get_pr_diff(owner, repo, pr_number)
                code = self.format_code_from_diff(diff)
                
                # Анализируем код PR через API
                response = send_request_to_api(code)
                if response:
                    analysis = parse_analysis(response["choices"][0]["message"]["content"])
                    if analysis:
                        # Сохраняем анализ каждого PR в отдельный файл
                        analysis_file = os.path.join(analysis_dir, f"pr_{pr_number}_analysis.json")
                        self.save_to_json(analysis, analysis_file)
                
                data = {
                    "author": pr["user"]["login"],
                    "code": code,
                    "id_pr": pr_number,
                    "link": pr["html_url"],
                    "created_at": datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S"),
                    "status": pr_status,
                    "closed_at": datetime.strptime(pr["closed_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S") if pr.get("closed_at") else None,
                    "merged_at": datetime.strptime(pr["merged_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S") if pr.get("merged_at") else None,
                    "commits": self.get_pr_commits(owner, repo, pr_number)
                }
                parsed_data.append(data)
                print(f"PR #{pr_number} успешно обработан")
            except Exception as e:
                print(f"Ошибка обработки PR #{pr_number}: {e}")
                continue

        return parsed_data

    def parse_mrs(self, owner, repo, save_to="mr_data.json"):
        return self._parse(owner, repo, "closed", save_to, merged_only=True)

    def _parse(self, owner, repo, state, save_to, merged_only=False):
        """
        Внутренний метод для парсинга pull request'ов.
        
        Args:
            owner (str): Владелец репозитория.
            repo (str): Название репозитория.
            state (str): Состояние PR (open/closed/all).
            save_to (str): Путь для сохранения данных.
            merged_only (bool, optional): Фильтр только для объединённых PR. По умолчанию False.
            
        Returns:
            list: Список словарей с данными о pull request'ах.
        """
        pr_list = self.get_pr_list(owner, repo, state=state)
        parsed_data = []

        for pr in pr_list:
            if merged_only and not pr.get("merged_at"):
                continue

            pr_number = pr["number"]
            try:
                diff = self.get_pr_diff(owner, repo, pr_number)
                data = {
                    "author": pr["user"]["login"],
                    "code": self.format_code_from_diff(diff),
                    "id_pr": pr_number,
                    "link": pr["html_url"],
                    "created_at": datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")
                }
                parsed_data.append(data)
            except Exception as e:
                print(f"Error processing PR #{pr_number}: {e}")
                continue

        # Если нужно сохранять данные в файл раскоментить
        # self.save_to_json(parsed_data, save_to)
        return parsed_data

    def save_to_json(self, data, filename):
        """
        Сохранение данных в JSON-файл.
        
        Args:
            data (list): Данные для сохранения.
            filename (str): Имя файла для сохранения.
            
        Raises:
            Exception: При ошибке сохранения данных.
        """
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"Data saved to {filename}")
        except Exception as e:
            print(f"Error saving to JSON: {e}")
            raise e

    def analyze_all_prs(self, repo_links, start_date=None, end_date=None, author_login=None, save_to="analysis_report.json"):
        """
        Получение и анализ pull request'ов из нескольких репозиториев за указанный период времени для указанного автора.
        
        Args:
            repo_links (list): Список ссылок на репозитории в формате 'https://github.com/owner/repo'.
            start_date (str, optional): Начальная дата периода в формате "YYYY-MM-DD". По умолчанию None (без ограничения).
            end_date (str, optional): Конечная дата периода в формате "YYYY-MM-DD". По умолчанию None (без ограничения).
            author_login (str, optional): Логин автора PR на GitHub для фильтрации. По умолчанию None (все авторы).
            save_to (str, optional): Путь для сохранения данных. По умолчанию "analysis_report.json".
            
        Returns:
            dict: Сводный анализ по всем репозиториям, или None если PR не найдены.
        """
        # Проверяем, что передан список ссылок
        if not repo_links:
            print("Ошибка: Не указаны ссылки на репозитории.")
            return None
        
        # Если передана одна ссылка как строка, преобразуем в список
        if isinstance(repo_links, str):
            repo_links = [repo_links]
        
        # Создаем директорию для анализов если её нет
        analysis_dir = os.path.join(os.path.dirname(__file__), "pr_files")
        os.makedirs(analysis_dir, exist_ok=True)
        
        all_prs_data = []
        all_prs_analysis_data = []
        
        # Паттерн для извлечения owner/repo из ссылки GitHub
        github_pattern = r"https://github\.com/([^/]+)/([^/]+)"
        
        # Обрабатываем каждый репозиторий
        for repo_link in repo_links:
            # Извлекаем owner и repo из ссылки
            match = re.match(github_pattern, repo_link)
            if not match:
                print(f"Неправильный формат ссылки на репозиторий: {repo_link}")
                continue
                
            owner, repo = match.groups()
            
            print(f"Анализ репозитория: {owner}/{repo}")
            
            # Получаем PR данные
            prs_data = self.parse_prs(owner, repo, start_date, end_date, author_login)
            
            # Проверяем есть ли PR
            if not prs_data:
                print(f"Предупреждение: PR не найдены для репозитория {owner}/{repo}")
                if author_login:
                    print(f"с логином: {author_login}")
                if start_date or end_date:
                    print(f"за период: {start_date or 'начало'} - {end_date or 'конец'}")
                continue
            
            # Выводим список полученных PR
            print(f"\nСписок полученных PR для репозитория {owner}/{repo}:")
            for i, pr in enumerate(prs_data, 1):
                print(f"{i}. PR #{pr['id_pr']} от {pr['created_at']} - Автор: {pr['author']} - {pr['link']}")
            print(f"Всего получено PR: {len(prs_data)}\n")
            
            all_prs_data.extend(prs_data)
            
            # Собираем данные по всем PR текущего репозитория для отправки в ИИ
            for pr in prs_data:
                analysis_file = os.path.join(analysis_dir, f"pr_{pr['id_pr']}_analysis.json")
                try:
                    with open(analysis_file, 'r', encoding='utf-8') as f:
                        analysis = json.load(f)
                        analysis['pr_info'] = {
                            'id': pr['id_pr'],
                            'author': pr['author'],
                            'link': pr['link'],
                            'created_at': pr['created_at'],
                            'repository': f"{owner}/{repo}"
                        }
                        all_prs_analysis_data.append(analysis)
                except FileNotFoundError:
                    print(f"Файл анализа не найден для PR #{pr['id_pr']}")
                    continue
        
        # Проверяем есть ли данные для анализа
        if not all_prs_analysis_data:
            print("Предупреждение: Нет данных для анализа PR во всех указанных репозиториях")
            
            # Создаем пустой отчет вместо возврата None
            empty_report = {
                "overall_score": "N/A",
                "recurring_issues": [],
                "antipatterns": [],
                "pr_status_stats": {
                    "open": 0,
                    "merged": 0,
                    "rejected": 0,
                    "total": 0
                }
            }
            
            # Сохраняем пустой отчет и создаем пустой полный отчет
            save_to_path = os.path.join(analysis_dir, save_to)
            if save_to:
                self.save_to_json(empty_report, save_to_path)
                self.create_full_report(empty_report, all_prs_data, [], save_to_path)
            
            return empty_report
            
        # Сохраняем отчет в папке pr_files
        save_to_path = os.path.join(analysis_dir, save_to)
        
        # Отправляем собранные данные на финальный анализ
        final_report = self.generate_final_report(all_prs_analysis_data)
        
        if final_report and save_to:
            self.save_to_json(final_report, save_to_path)
            # Создаем полный отчет после сохранения основного анализа
            self.create_full_report(final_report, all_prs_data, all_prs_analysis_data, save_to_path)
        
        return final_report

    def create_full_report(self, final_report, prs_data, prs_analysis_data, analysis_report_path):
        """Создает полный отчет, включающий общий анализ и детальный анализ каждого PR"""
        full_report = {
            "общий_анализ": final_report,
            "детальный_анализ": []
        }
        
        # Собираем детальный анализ по каждому PR
        for pr_files in prs_analysis_data:
            pr_id = pr_files['pr_info']['id']
            # Находим соответствующие данные PR
            pr_data = next((pr for pr in prs_data if pr['id_pr'] == pr_id), None)
            if pr_data:
                pr_files['pr_info']['commits'] = pr_data['commits']
                # Добавляем статус PR в информацию
                pr_files['pr_info']['status'] = pr_data.get('status', 'open')
                pr_files['pr_info']['closed_at'] = pr_data.get('closed_at')
                pr_files['pr_info']['merged_at'] = pr_data.get('merged_at')
                full_report["детальный_анализ"].append(pr_files)
        
        # Добавляем статистику по статусам PR
        status_stats = {
            "open": 0,
            "merged": 0,
            "rejected": 0,
            "total": len(prs_data)
        }
        
        for pr in prs_data:
            status = pr.get('status', 'open')
            if status in status_stats:
                status_stats[status] += 1
        
        # Добавляем статистику в общий анализ
        if final_report:
            final_report["pr_status_stats"] = status_stats
        
        # Сохраняем полный отчет
        full_report_path = analysis_report_path.replace('.json', '_full.json')
        self.save_to_json(full_report, full_report_path)
        print(f"Полный отчет сохранен в {full_report_path}")

    def generate_final_report(self, prs_analysis_data):
        instruction = """Проанализируй данные по всем PR и создай итоговый отчет в следующем формате. 
        {
            "overall_score": number,
            "recurring_issues": [
                {"issue": "общее описание проблемы, do not specify the name of methods, classes, files, etc."},
            ],
            "antipatterns": [
                {"name": "название антипаттерна и его общее описание"}
            ]
        }"""
        
        # Используем относительный путь к директории анализа
        base_dir = os.path.dirname(__file__)
        analysis_dir = os.path.join(base_dir, "pr_files")
        os.makedirs(analysis_dir, exist_ok=True)
        
        # Обрабатываем все PR без ограничения по количеству
        analysis_batch = prs_analysis_data
        
        # Сохраняем пример запроса в файл в папке pr_files
        prompt = instruction + "\n" + json.dumps(analysis_batch, ensure_ascii=False, indent=2)
        report_file = os.path.join(analysis_dir, "final_report_prompt.txt")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(prompt)
        
        # Добавляем повторные попытки отправки запроса
        retries = 0
        while retries < MAX_ANALYSIS_RETRIES:
            try:
                print(f"Отправка запроса для анализа PR (попытка {retries+1}/{MAX_ANALYSIS_RETRIES})...")
                response = send_request_to_api(prompt)
                
                if response and "choices" in response:
                    result = parse_analysis(response["choices"][0]["message"]["content"])
                    if result:
                        return result
                
                # Если результат пустой или неверный формат, повторяем попытку
                print(f"Получен некорректный ответ от API, повтор через {RETRY_INTERVAL} сек...")
                retries += 1
                time.sleep(RETRY_INTERVAL)
            except Exception as e:
                print(f"Ошибка при анализе PR: {str(e)}")
                retries += 1
                if retries < MAX_ANALYSIS_RETRIES:
                    print(f"Повторная попытка через {RETRY_INTERVAL} сек...")
                    time.sleep(RETRY_INTERVAL)
                else:
                    print("Все попытки анализа исчерпаны.")
        
        # Если все попытки неудачны, возвращаем пустой отчет вместо None
        return {
            "overall_score": "N/A",
            "recurring_issues": [],
            "antipatterns": []
        }

def main():
    parser = GitHubParser()
    results = parser.analyze_all_prs(["https://github.com/microsoft/vscode-docs"], start_date=None, end_date=None, author_login="mrljtster", save_to="analysis_report.json")
    print(f"Получено PR: {len(results)}")

if __name__ == "__main__":
    main()