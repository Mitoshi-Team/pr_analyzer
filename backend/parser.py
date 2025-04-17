import requests
from datetime import datetime
import json
import sys
from сode_analysis import send_request_to_api, parse_analysis
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()


class GitHubParser:
    def __init__(self, token=None):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        # Используем токен из переменных окружения, если не передан явно
        if token is None:
            token = os.getenv("GITHUB_TOKEN")
        if token:
            self.headers["Authorization"] = f"token {token}"


    def get_pr_list(self, owner, repo, state="open"):
        """
        Получение списка pull request'ов из репозитория.
        
        Args:
            owner (str): Владелец репозитория.
            repo (str): Название репозитория.
            state (str, optional): Состояние PR (open/closed/all). По умолчанию "open".
            
        Returns:
            list: Список pull request'ов.
            
        Raises:
            requests.exceptions.HTTPError: Если произошла ошибка HTTP.
            Exception: При других ошибках.
        """
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state={state}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 403:
                print("Rate limit exceeded. Consider using a GitHub token or wait before retrying.")
            raise e
        except Exception as e:
            print(f"Error fetching PR list: {e}")
            raise e


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


    def get_pr_commits(self, owner, repo, pr_number):
        """Получает информацию о коммитах PR"""
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


    def parse_prs(self, owner, repo, start_date=None, end_date=None, author_email=None, save_to="pr_data.json"):
        """
        Получение и анализ pull request'ов из репозитория за указанный период времени для указанного автора.
        
        Args:
            owner (str): Владелец репозитория.
            repo (str): Название репозитория.
            start_date (str, optional): Начальная дата периода в формате "YYYY-MM-DD". По умолчанию None (без ограничения).
            end_date (str, optional): Конечная дата периода в формате "YYYY-MM-DD". По умолчанию None (без ограничения).
            author_email (str, optional): Почта автора PR для фильтрации. По умолчанию None (все авторы).
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
        
        pr_list = self.get_pr_list(owner, repo, state="all")  # Получаем все PR для последующей фильтрации
        parsed_data = []

        for pr in pr_list:
            # Проверяем, соответствует ли PR заданному периоду времени
            pr_created_at = datetime.strptime(pr["created_at"], "%Y-%m-%dT%H:%M:%SZ")
            
            # Фильтрация по дате
            if start_datetime and pr_created_at < start_datetime:
                continue
            if end_datetime and pr_created_at > end_datetime:
                continue
                
            # Получаем информацию о пользователе для проверки email
            if author_email:
                # GitHub API не возвращает email в базовом запросе PR
                # Нужно получить детальную информацию о пользователе
                try:
                    user_url = pr["user"]["url"]
                    user_response = requests.get(user_url, headers=self.headers)
                    user_response.raise_for_status()
                    user_data = user_response.json()
                    
                    # Проверяем соответствие email
                    user_email = user_data.get("email")
                    if not user_email or user_email.lower() != author_email.lower():
                        continue
                except Exception as e:
                    print(f"Ошибка при получении информации о пользователе: {e}")
                    continue
            
            pr_number = pr["number"]
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
                    "commits": self.get_pr_commits(owner, repo, pr_number)
                }
                parsed_data.append(data)
            except Exception as e:
                print(f"Error processing PR #{pr_number}: {e}")
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
        import os
        import re
        
        # Проверяем, что передан список ссылок
        if not repo_links:
            print("Ошибка: Не указаны ссылки на репозитории.")
            return None
        
        # Если передана одна ссылка как строка, преобразуем в список
        if isinstance(repo_links, str):
            repo_links = [repo_links]
        
        # Создаем директорию для анализов если её нет
        base_dir = os.path.dirname(__file__)
        analysis_dir = os.path.join(base_dir, "pr_files")
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
            prs_data = self.parse_prs(owner, repo, start_date, end_date, None)
            
            # Если указан автор, фильтруем PR по логину автора
            if author_login and prs_data:
                prs_data = [pr for pr in prs_data if pr["author"].lower() == author_login.lower()]
            
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
            return None
            
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
                full_report["детальный_анализ"].append(pr_files)
        
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
        
        # Сохраняем пример запроса в файл в папке pr_files
        prompt = instruction + "\n" + json.dumps(prs_analysis_data, ensure_ascii=False, indent=2)
        report_file = os.path.join(analysis_dir, "final_report_prompt.txt")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(prompt)
            
        response = send_request_to_api(prompt)
        if response and "choices" in response:
            return parse_analysis(response["choices"][0]["message"]["content"])
        return None


parser = GitHubParser()
# Передаем параметры для фильтрации PR по дате и автору
# https://github.com/microsoft/vscode-extension-samples
results = parser.analyze_all_prs(["https://github.com/microsoft/vscode-extension-samples"], start_date=None, end_date=None, author_login="mrljtster", save_to="analysis_report.json")
