import os
from pathlib import Path
import re
import requests
import yaml

from cff_author_updater.contributors.git_commit_contributor import GitCommitContributor
from cff_author_updater.contributors.github_user_contributor import (
    GitHubUserContributor,
)
from cff_author_updater.flags import Flags

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
        self,
        token: str,
        repo: str,
        pr_number: str,
        bot_blacklist: set | None = None,
    ) -> tuple[set, dict]:
        if bot_blacklist is None:
            bot_blacklist = set()

        session: requests.Session = self.get_github_session(token=token)
        contributors: set = set()
        contribution_details: dict = {}

        if Flags.has("authorship_for_pr_reviews"):
            reviews_url = (
                f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
            )
            for review in session.get(reviews_url).json():
                github_username = review.get("user", {}).get("login")
                url = review.get("html_url")
                if github_username and github_username not in bot_blacklist:
                    contributor: GitHubUserContributor = GitHubUserContributor(
                        github_username=github_username
                    )
                    contributors.add(contributor)
                    contribution_details.setdefault(contributor, {}).setdefault(
                        "reviews", []
                    ).append(url)

        if Flags.has("authorship_for_pr_comment"):
            comments_url: str = (
                f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            )
            for comment in session.get(comments_url).json():
                github_username = comment.get("user", {}).get("login")
                url = comment.get("html_url")
                if github_username and github_username not in bot_blacklist:
                    contributor: GitHubUserContributor = GitHubUserContributor(
                        github_username=github_username
                    )
                    contributors.add(contributor)
                    contribution_details.setdefault(contributor, {}).setdefault(
                        "pr_comments", []
                    ).append(url)

        if Flags.has("authorship_for_pr_issues") or Flags.has(
            "authorship_for_pr_issue_comments"
        ):
            linked_issues = self.get_linked_issues(
                session=session, repo=repo, pr_number=pr_number
            )
            for issue_number in linked_issues:
                if Flags.has("authorship_for_pr_issues"):
                    issue_url: str = (
                        f"https://api.github.com/repos/{repo}/issues/{issue_number}"
                    )
                    issue = session.get(issue_url).json()
                    github_username = issue.get("user", {}).get("login")
                    url = issue.get("html_url")
                    if github_username and github_username not in bot_blacklist:
                        contributor: GitHubUserContributor = GitHubUserContributor(
                            github_username=github_username
                        )
                        contributors.add(contributor)
                        contribution_details.setdefault(contributor, {}).setdefault(
                            "issues", []
                        ).append(url)

                if Flags.has("authorship_for_pr_issue_comments"):
                    comments_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
                    for comment in session.get(comments_url).json():
                        github_username = comment.get("user", {}).get("login")
                        url = comment.get("html_url")
                        if github_username and github_username not in bot_blacklist:
                            contributor: GitHubUserContributor = GitHubUserContributor(
                                github_username=github_username
                            )
                            contributors.add(contributor)
                            contribution_details.setdefault(contributor, {}).setdefault(
                                "issue_comments", []
                            ).append(url)

        return contributors, contribution_details

    def collect_commit_contributors(
        self,
        token: str,
        repo: str,
        base: str,
        head: str,
        bot_blacklist=None,
    ):
        if bot_blacklist is None:
            bot_blacklist = set()

        url: str = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
        headers: dict = {"Authorization": f"token {token}"}
        r: requests.Response = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        commits: list = data.get("commits", [])
        contributors = set()
        contribution_details: dict = {}
        coauthor_regex = re.compile(
            r"^Co-authored-by:\s*(.+?)\s*<(.+?)>$", re.IGNORECASE
        )

        for c in commits:
            sha: str = c.get("sha")
            commit_author = c.get("commit", {}).get("author", {})
            github_author = c.get("author")

            if github_author and github_author.get("login"):
                username = github_author["login"]
                if username not in bot_blacklist:
                    contributor = GitHubUserContributor(github_username=username)
                    contributors.add(contributor)
                    contribution_details.setdefault(contributor, {}).setdefault(
                        "commits", []
                    ).append(sha)
            elif commit_author:
                name = commit_author.get("name")
                if name in bot_blacklist:
                    break
                email = commit_author.get("email")
                if name or email:
                    contributor = GitCommitContributor(
                        git_name=name.strip(), git_email=email.strip()
                    )
                    contributors.add(contributor)
                    contribution_details.setdefault(contributor, {}).setdefault(
                        "commits", []
                    ).append(sha)
                else:
                    contribution_details.setdefault(
                        UNKNOWN_CONTRIBUTOR_KEY, {}
                    ).setdefault("commits", []).append(sha)

            # add coauthors
            for line in c.get("commit", {}).get("message", "").splitlines():
                match = coauthor_regex.match(line.strip())
                if match:
                    name, email = match.groups()
                    if name not in bot_blacklist:
                        key = (name.strip(), email.strip())
                        contributors.add(key)
                        contribution_details.setdefault(key, {}).setdefault(
                            "commits", []
                        ).append(sha)

        return sorted(contributors), contribution_details

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
        self,
        cff_path: Path,
        cff: dict,
        warnings: list,
        logs: list,
        token: str,
        repo: str,
        pr_number: str,
        contribution_details: dict,
        repo_for_compare: str,
        missing_authors: set,
        missing_author_invalidates_pr: bool,
    ):

        marker: str = "<!-- contributor-check-comment -->"
        timestamp = (
            requests.get("https://timeapi.io/api/Time/current/zone?timeZone=UTC")
            .json()
            .get("dateTime", "")[:16]
            .replace("T", " ")
        )
        commit_sha = os.environ.get("GITHUB_SHA", "")
        commit_sha_short = commit_sha[:7]
        commit_url = f"https://github.com/{repo}/commit/{commit_sha}"

        # Add contribution details per new author
        comment_contributions = "\n**New Authors & Contributions:**\n"
        new_authors = contribution_details.keys() - {UNKNOWN_CONTRIBUTOR_KEY}
        if new_authors:
            for new_author in new_authors:
                if new_author in missing_authors:
                    missing_author_message = f" (Missing from `{cff_path}`)"
                else:
                    missing_author_message = ""
                if isinstance(new_author, GitHubUserContributor):
                    # github user
                    comment_contributions += (
                        f"\n#### @{new_author}{missing_author_message}\n"
                    )
                elif isinstance(new_author, GitCommitContributor):
                    # non github committer
                    new_author_name = new_author.git_name
                    new_author_email = new_author.git_email
                    if new_author_email:
                        comment_contributions += (
                            f"\n#### {new_author_email}{missing_author_message}\n"
                        )
                    else:
                        comment_contributions += (
                            f"\n#### {new_author_name}{missing_author_message}\n"
                        )
                else:
                    raise Exception(
                        "Invalid new_author: It must be a GitHubUserContributor or a GitCommitContributor."
                    )

                details = contribution_details.get(new_author, {})
                for category, items in details.items():
                    comment_contributions += (
                        f"- **{category.replace('_', ' ').title()}**\n"
                    )
                    for item in items:
                        if category == "commits":
                            comment_contributions += f"  - [`{item[:7]}`](https://github.com/{repo_for_compare}/commit/{item})\n"
                        else:
                            comment_contributions += f"  - [Link]({item})\n"
        else:
            comment_contributions += "\n**No new authors.**\n"

        comment_body = f"""
{marker}
### CFF Author Updater ###

{comment_contributions}
"""
        if missing_authors:
            comment_body += f"""
**Recommended `{cff_path}` file (updated with missing authors):**
```yaml
{yaml.dump(cff, sort_keys=False)}
```
"""
            comment_body += f"***Important: This recommended `{cff_path}` file has not been changed yet on this pull request. It can be manually copied and committed to the repository. For Github users to be recognized, you must use their Github user profile URL as their `alias` in the {cff_path} file."
            if missing_author_invalidates_pr:
                comment_body += f" If the `{cff_path}` file is missing any new author, the pull request will remain invalid."
            comment_body += f"***"
        else:
            comment_body += f"**Current `{cff_path}` file contains all new authors.**"
        if warnings:
            comment_body += "\n\n**Warnings:**\n" + "\n".join(warnings)

        if logs:
            comment_body += f"""

<details>
<summary><strong>ORCID Match Details</strong></summary>

{chr(10).join(logs)}

</details>"""

        comment_body += f"""

_Last updated: {timestamp} UTC · Commit [`{commit_sha_short}`]({commit_url})_

***Powered by [CFF Author Updater v{self.github_action_version}](https://github.com/willynilly/cff-author-updater)***
"""

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
