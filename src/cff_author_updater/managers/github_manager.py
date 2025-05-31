from datetime import datetime, timezone
import os
from pathlib import Path
import re
import requests
import yaml

from cff_author_updater.cff_author_review import CffAuthorReview
from cff_author_updater.cff_file import CffFile
from cff_author_updater.contributions.github_pull_request_comment_contribution import (
    GitHubPullRequestCommentContribution,
)
from cff_author_updater.contributions.github_pull_request_commit_contribution import (
    GitHubPullRequestCommitContribution,
)
from cff_author_updater.contributions.github_pull_request_issue_comment_contribution import (
    GitHubPullRequestIssueCommentContribution,
)
from cff_author_updater.contributions.github_pull_request_issue_contribution import (
    GitHubPullRequestIssueContribution,
)
from cff_author_updater.contributions.github_pull_request_review_contribution import (
    GitHubPullRequestReviewContribution,
)
from cff_author_updater.contributors.git_commit_contributor import GitCommitContributor
from cff_author_updater.contributors.github_contributor import (
    GitHubContributor,
)
from cff_author_updater.flags import Flags
from cff_author_updater.logging_config import get_log_collector
from cff_author_updater.managers.contribution_manager import ContributionManager

UNKNOWN_CONTRIBUTOR_KEY = ("unknown", None)


class GithubManager:

    def __init__(self):
        self.github_action_version = self.get_github_action_version()

    def get_github_session(self, token) -> requests.Session:
        session: requests.Session = requests.Session()
        session.headers.update(
            {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        )
        return session

    def get_linked_issues(self, session: requests.Session, repo: str, pr_number: str):
        url: str = f"https://api.github.com/repos/{repo}/issues/{pr_number}/timeline"
        headers: dict = {"Accept": "application/vnd.github.mockingbird-preview+json"}
        response: requests.Response = session.get(url, headers=headers)
        if response.status_code != 200:
            return []
        data = response.json()
        return [
            event["source"]["issue"]["number"]
            for event in data
            if event.get("event") == "cross-referenced"
            and event.get("source", {}).get("issue", {}).get("pull_request") is None
        ]

    def collect_metadata_contributors(
        self, token: str, repo: str, pr_number: str, bot_blacklist: set | None = None
    ) -> ContributionManager:
        if bot_blacklist is None:
            bot_blacklist = set()

        session: requests.Session = self.get_github_session(token=token)
        contribution_manager = ContributionManager()

        # PR Reviews
        if Flags.has("authorship_for_pr_reviews"):
            reviews_url = (
                f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
            )
            for review in session.get(reviews_url).json():
                github_username = review.get("user", {}).get("login")
                url = review.get("html_url")
                created_at_str = review.get("submitted_at")
                created_at = (
                    datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
                    if created_at_str
                    else datetime.min
                )
                if github_username and github_username not in bot_blacklist:
                    contributor = GitHubContributor(github_username=github_username)
                    contribution = GitHubPullRequestReviewContribution(
                        id=url, created_at=created_at
                    )
                    contribution_manager.add_contribution(contribution, contributor)

        # PR Comments
        if Flags.has("authorship_for_pr_comments"):
            comments_url = (
                f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            )
            for comment in session.get(comments_url).json():
                github_username = comment.get("user", {}).get("login")
                url = comment.get("html_url")
                created_at_str = comment.get("created_at")
                created_at = (
                    datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
                    if created_at_str
                    else datetime.min
                )
                if github_username and github_username not in bot_blacklist:
                    contributor = GitHubContributor(github_username=github_username)
                    contribution = GitHubPullRequestCommentContribution(
                        id=url, created_at=created_at
                    )
                    contribution_manager.add_contribution(contribution, contributor)

        # Linked Issues and Issue Comments
        if Flags.has("authorship_for_pr_issues") or Flags.has(
            "authorship_for_pr_issue_comments"
        ):
            linked_issues = self.get_linked_issues(
                session=session, repo=repo, pr_number=pr_number
            )
            for issue_number in linked_issues:

                # PR Issues
                if Flags.has("authorship_for_pr_issues"):
                    issue_url = (
                        f"https://api.github.com/repos/{repo}/issues/{issue_number}"
                    )
                    issue = session.get(issue_url).json()
                    github_username = issue.get("user", {}).get("login")
                    url = issue.get("html_url")
                    created_at_str = issue.get("created_at")
                    created_at = (
                        datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
                        if created_at_str
                        else datetime.min
                    )
                    if github_username and github_username not in bot_blacklist:
                        contributor = GitHubContributor(github_username=github_username)
                        contribution = GitHubPullRequestIssueContribution(
                            id=url, created_at=created_at
                        )
                        contribution_manager.add_contribution(contribution, contributor)

                # PR Issue Comments
                if Flags.has("authorship_for_pr_issue_comments"):
                    comments_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
                    for comment in session.get(comments_url).json():
                        github_username = comment.get("user", {}).get("login")
                        url = comment.get("html_url")
                        created_at_str = comment.get("created_at")
                        created_at = (
                            datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
                            if created_at_str
                            else datetime.min
                        )
                        if github_username and github_username not in bot_blacklist:
                            contributor = GitHubContributor(
                                github_username=github_username
                            )
                            contribution = GitHubPullRequestIssueCommentContribution(
                                id=url, created_at=created_at
                            )
                            contribution_manager.add_contribution(
                                contribution, contributor
                            )

        return contribution_manager

    def collect_commit_contributors(
        self, token: str, repo: str, base: str, head: str, bot_blacklist=None
    ) -> ContributionManager:
        if bot_blacklist is None:
            bot_blacklist = set()

        url = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
        headers = {"Authorization": f"token {token}"}
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        commits = data.get("commits", [])

        contribution_manager = ContributionManager()
        coauthor_regex = re.compile(
            r"^Co-authored-by:\s*(.+?)\s*<(.+?)>$", re.IGNORECASE
        )

        for c in commits:
            sha = c.get("sha")
            commit_author_data = c.get("commit", {}).get("author", {})
            github_author = c.get("author")

            commit_date_str = commit_author_data.get("date")
            commit_date = (
                datetime.strptime(commit_date_str, "%Y-%m-%dT%H:%M:%SZ")
                if commit_date_str
                else datetime.min
            )

            if github_author and github_author.get("login"):
                username = github_author["login"]
                if username not in bot_blacklist:
                    contributor = GitHubContributor(github_username=username)
                    contribution = GitHubPullRequestCommitContribution(
                        sha=sha, created_at=commit_date
                    )
                    contribution_manager.add_contribution(contribution, contributor)
            elif commit_author_data:
                name = commit_author_data.get("name")
                if name in bot_blacklist:
                    continue
                email = commit_author_data.get("email")
                if name or email:
                    contributor = GitCommitContributor(
                        git_name=name.strip(), git_email=email.strip()
                    )
                    contribution = GitHubPullRequestCommitContribution(
                        sha=sha, created_at=commit_date
                    )
                    contribution_manager.add_contribution(contribution, contributor)

            # add coauthors
            for line in c.get("commit", {}).get("message", "").splitlines():
                match = coauthor_regex.match(line.strip())
                if match:
                    name, email = match.groups()
                    if name not in bot_blacklist:
                        contributor = GitCommitContributor(
                            git_name=name.strip(), git_email=email.strip()
                        )
                        contribution = GitHubPullRequestCommitContribution(
                            sha=sha, created_at=commit_date
                        )
                        contribution_manager.add_contribution(contribution, contributor)

        return contribution_manager

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

    def post_pull_request_comment(
        self, token: str, repo: str, pr_number: str, comment_body: str
    ):

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        comments_url = (
            f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        )

        payload = {"body": comment_body}
        resp: requests.Response = requests.post(
            comments_url, headers=headers, json=payload
        )
        resp.raise_for_status()
