import json
import logging
import os
from pathlib import Path

import requests
import yaml

from cff_author_updater.managers.orcid_manager import OrcidManager

logger = logging.getLogger(__name__)


class GitHubManager:
    def __init__(self):
        self.github_action_version = self.get_github_action_version()
        self._load_from_environment_variables()
        self.orcid_manager = OrcidManager()

    def _load_from_environment_variables(self):

        self.repo: str = os.environ["REPO"]
        self.github_token: str = os.environ["GITHUB_TOKEN"]
        self.output_file: str = os.environ.get(
            "GITHUB_OUTPUT", "/tmp/github_output.txt"
        )
        self.github_event_path: Path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))

        if self.github_event_path and self.github_event_path.exists():
            with open(self.github_event_path, "r") as f:
                event = json.load(f)
                self._load_github_event(event)
        else:
            raise Exception("GITHUB_EVENT_PATH is missing.")

    def get_github_session(self, token) -> requests.Session:
        session: requests.Session = requests.Session()
        session.headers.update(
            {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        )
        return session

    def get_github_action_version(self) -> str:
        action_root = (
            Path(os.environ.get("GITHUB_ACTION_PATH", ""))
            if "GITHUB_ACTION_PATH" in os.environ
            else Path(__file__).resolve().parent.parent.parent
        )
        cff_path = action_root / "CITATION.cff"

        if not cff_path.exists():
            raise FileNotFoundError(f"CITATION.cff not found at: {cff_path}")

        with cff_path.open("r") as f:
            cff_data = yaml.safe_load(f)

        return cff_data.get("version", "")
    
    def get_github_user_profile(self, github_username: str) -> dict | None:
        url = f"https://api.github.com/users/{github_username}"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "cff-author-updater",
        }
        if self.github_token:
            headers["Authorization"] = f"Bearer {self.github_token}"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            return {
                "login": data.get("login", ""),
                "name": data.get("name", ""),
                "bio": data.get("bio", ""),
                "blog": data.get("blog", ""),
                "email": data.get("email", ""),
                "type": data.get("type", "User"),
            }

        except requests.RequestException:
            msg = f"Invalid GitHub username: failed to find GitHub user profile for @{github_username}"
            logger.error(msg)
            return None


    def _load_github_event(self, event: dict):
        pass
