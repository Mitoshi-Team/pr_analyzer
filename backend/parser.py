import requests
from datetime import datetime
import json
import sys
from backend.сode_analysis import send_request_to_api, parse_analysis


class GitHubParser:
    def __init__(self, token='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'):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
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


    def parse_prs(self, owner, repo, save_to="pr_data.json"):
        import os
        
        # Создаем директорию для анализов если её нет
        analysis_dir = "D:\\alpha_insurance\\backend\\pr_analysis"
        os.makedirs(analysis_dir, exist_ok=True)
        
        pr_list = self.get_pr_list(owner, repo, state="open")
        parsed_data = []

        for pr in pr_list:
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


    def analyze_all_prs(self, owner, repo, save_to="analysis_report.json"):
        import os
        
        prs_data = self.parse_prs(owner, repo)
        save_to = "D:\\alpha_insurance\\backend\\" + save_to
        
        # Собираем данные по всем PR для отправки в ИИ
        prs_analysis_data = []
        
        analysis_dir = "D:\\alpha_insurance\\backend\\pr_analysis"
        for pr in prs_data:
            analysis_file = os.path.join(analysis_dir, f"pr_{pr['id_pr']}_analysis.json")
            try:
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    analysis = json.load(f)
                    analysis['pr_info'] = {
                        'id': pr['id_pr'],
                        'author': pr['author'],
                        'link': pr['link'],
                        'created_at': pr['created_at']
                    }
                    prs_analysis_data.append(analysis)
            except FileNotFoundError:
                print(f"Файл анализа не найден для PR #{pr['id_pr']}")
                continue

        # Отправляем собранные данные на финальный анализ
        final_report = self.generate_final_report(prs_analysis_data)
        
        if save_to:
            self.save_to_json(final_report, save_to)
            # Создаем полный отчет после сохранения основного анализа
            self.create_full_report(final_report, prs_data, prs_analysis_data, save_to)
        
        return final_report

    def create_full_report(self, final_report, prs_data, prs_analysis_data, analysis_report_path):
        """Создает полный отчет, включающий общий анализ и детальный анализ каждого PR"""
        full_report = {
            "общий_анализ": final_report,
            "детальный_анализ": []
        }
        
        # Собираем детальный анализ по каждому PR
        for pr_analysis in prs_analysis_data:
            pr_id = pr_analysis['pr_info']['id']
            # Находим соответствующие данные PR
            pr_data = next((pr for pr in prs_data if pr['id_pr'] == pr_id), None)
            if pr_data:
                pr_analysis['pr_info']['commits'] = pr_data['commits']
                full_report["детальный_анализ"].append(pr_analysis)
        
        # Сохраняем полный отчет
        full_report_path = analysis_report_path.replace('.json', '_full.json')
        self.save_to_json(full_report, full_report_path)
        print(f"Полный отчет сохранен в {full_report_path}")

    def generate_final_report(self, prs_analysis_data):
        instruction = """Проанализируй данные по всем PR и создай итоговый отчет в следующем формате. 
        {
            "общая_оценка": число,
            "повторяющиеся_проблемы": [
                {"проблема": "общее описание проблемы, do not specify the name of methods, classes, files, etc."},
            ],
            "антипаттерны": [
                {"название": "название антипаттерна и его общее описание"}
            ]
        }"""
        
        # Сохраняем пример запроса в файл
        prompt = instruction + "\n" + json.dumps(prs_analysis_data, ensure_ascii=False, indent=2)
        with open("D:\\alpha_insurance\\final_report_prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
            
        response = send_request_to_api(prompt)
        if response and "choices" in response:
            return parse_analysis(response["choices"][0]["message"]["content"])
        return None


parser = GitHubParser()
results = parser.analyze_all_prs("microsoft", "vscode-extension-samples", "analysis_report.json")
