import json
import os
from pathlib import Path

import requests
import yaml


class GitHubManager:
    def __init__(self):
        self.github_action_version = self.get_github_action_version()
        self._load_from_environment_variables()

    def _load_from_environment_variables(self):

        self.repo: str = os.environ["REPO"]
        self.token: str = os.environ["GITHUB_TOKEN"]
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

    def _load_github_event(self, event: dict):
        pass
