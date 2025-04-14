import requests
from datetime import datetime
import json
import sys


class GitHubParser:
    def __init__(self, token=None):
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            self.headers["Authorization"] = f"token {token}"


    def get_pr_list(self, owner, repo, state="open"):
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


    def parse_prs(self, owner, repo, save_to="pr_data.json"):
        return self._parse(owner, repo, "open", save_to)


    def parse_mrs(self, owner, repo, save_to="mr_data.json"):
        return self._parse(owner, repo, "closed", save_to, merged_only=True)


    def _parse(self, owner, repo, state, save_to, merged_only=False):
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
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"Data saved to {filename}")
        except Exception as e:
            print(f"Error saving to JSON: {e}")
            raise e
