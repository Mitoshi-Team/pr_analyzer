import requests
from datetime import datetime
import json
import sys


class GitHubParser:
    """
    Класс для работы с GitHub API и получения данных о pull request'ах.
    """
    def __init__(self, token=None):
        """
        Инициализация GitHubParser.
        
        Args:
            token (str, optional): GitHub API токен для авторизации запросов.
        """
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


    def parse_prs(self, owner, repo, state="open", save_to="pr_data.json"):
        """
        Парсинг открытых pull request'ов из репозитория.
        
        Args:
            owner (str): Владелец репозитория.
            repo (str): Название репозитория.
            save_to (str, optional): Путь для сохранения данных. По умолчанию "pr_data.json".
            
        Returns:
            list: Список словарей с данными о pull request'ах.
        """
        return self._parse(owner, repo, state, save_to)


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