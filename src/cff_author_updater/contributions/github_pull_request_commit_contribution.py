from datetime import datetime
from cff_author_updater.contributions.contribution import Contribution


class GitHubPullRequestCommitContribution(Contribution):

    def __init__(self, sha: str, created_at: datetime):
        super().__init__(id=sha, created_at=created_at)
        self.sha = sha

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["sha"] = self.sha
        return data
