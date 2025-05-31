from datetime import datetime, timezone
import os
from pathlib import Path
import re
import requests
import yaml

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

    # def collect_metadata_contributors(
    #     self, token: str, repo: str, pr_number: str, bot_blacklist: set | None = None
    # ) -> ContributionManager:
    #     if bot_blacklist is None:
    #         bot_blacklist = set()

    #     session: requests.Session = self.get_github_session(token=token)
    #     contribution_manager = ContributionManager()

    #     if Flags.has("authorship_for_pr_reviews"):
    #         reviews_url = (
    #             f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
    #         )
    #         for review in session.get(reviews_url).json():
    #             github_username = review.get("user", {}).get("login")
    #             url = review.get("html_url")
    #             if github_username and github_username not in bot_blacklist:
    #                 contributor = GitHubContributor(github_username=github_username)
    #                 contribution = Contribution(id=url)
    #                 contribution_manager.add_contribution(contribution, contributor)

    #     if Flags.has("authorship_for_pr_comments"):
    #         comments_url = (
    #             f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    #         )
    #         for comment in session.get(comments_url).json():
    #             github_username = comment.get("user", {}).get("login")
    #             url = comment.get("html_url")
    #             if github_username and github_username not in bot_blacklist:
    #                 contributor = GitHubContributor(github_username=github_username)
    #                 contribution = Contribution(id=url)
    #                 contribution_manager.add_contribution(contribution, contributor)

    #     if Flags.has("authorship_for_pr_issues") or Flags.has(
    #         "authorship_for_pr_issue_comments"
    #     ):
    #         linked_issues = self.get_linked_issues(
    #             session=session, repo=repo, pr_number=pr_number
    #         )
    #         for issue_number in linked_issues:
    #             if Flags.has("authorship_for_pr_issues"):
    #                 issue_url = (
    #                     f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    #                 )
    #                 issue = session.get(issue_url).json()
    #                 github_username = issue.get("user", {}).get("login")
    #                 url = issue.get("html_url")
    #                 if github_username and github_username not in bot_blacklist:
    #                     contributor = GitHubContributor(github_username=github_username)
    #                     contribution = Contribution(id=url)
    #                     contribution_manager.add_contribution(contribution, contributor)

    #             if Flags.has("authorship_for_pr_issue_comments"):
    #                 comments_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    #                 for comment in session.get(comments_url).json():
    #                     github_username = comment.get("user", {}).get("login")
    #                     url = comment.get("html_url")
    #                     if github_username and github_username not in bot_blacklist:
    #                         contributor = GitHubContributor(
    #                             github_username=github_username
    #                         )
    #                         contribution = Contribution(id=url)
    #                         contribution_manager.add_contribution(
    #                             contribution, contributor
    #                         )

    #     return contribution_manager

    # def collect_commit_contributors(
    #     self,
    #     token: str,
    #     repo: str,
    #     base: str,
    #     head: str,
    #     bot_blacklist=None,
    # ):
    #     if bot_blacklist is None:
    #         bot_blacklist = set()

    #     url: str = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
    #     headers: dict = {"Authorization": f"token {token}"}
    #     r: requests.Response = requests.get(url, headers=headers)
    #     r.raise_for_status()
    #     data = r.json()
    #     commits: list = data.get("commits", [])
    #     contributors = set()
    #     contribution_details: dict = {}
    #     coauthor_regex = re.compile(
    #         r"^Co-authored-by:\s*(.+?)\s*<(.+?)>$", re.IGNORECASE
    #     )

    #     for c in commits:
    #         sha: str = c.get("sha")
    #         commit_author = c.get("commit", {}).get("author", {})
    #         github_author = c.get("author")

    #         if github_author and github_author.get("login"):
    #             username = github_author["login"]
    #             if username not in bot_blacklist:
    #                 contributor = GitHubContributor(github_username=username)
    #                 contributors.add(contributor)
    #                 contribution_details.setdefault(contributor, {}).setdefault(
    #                     "commits", []
    #                 ).append(sha)
    #         elif commit_author:
    #             name = commit_author.get("name")
    #             if name in bot_blacklist:
    #                 break
    #             email = commit_author.get("email")
    #             if name or email:
    #                 contributor = GitCommitContributor(
    #                     git_name=name.strip(), git_email=email.strip()
    #                 )
    #                 contributors.add(contributor)
    #                 contribution_details.setdefault(contributor, {}).setdefault(
    #                     "commits", []
    #                 ).append(sha)
    #             else:
    #                 contribution_details.setdefault(
    #                     UNKNOWN_CONTRIBUTOR_KEY, {}
    #                 ).setdefault("commits", []).append(sha)

    #         # add coauthors
    #         for line in c.get("commit", {}).get("message", "").splitlines():
    #             match = coauthor_regex.match(line.strip())
    #             if match:
    #                 name, email = match.groups()
    #                 if name not in bot_blacklist:
    #                     key = (name.strip(), email.strip())
    #                     contributors.add(key)
    #                     contribution_details.setdefault(key, {}).setdefault(
    #                         "commits", []
    #                     ).append(sha)

    #     return sorted(contributors), contribution_details

    # def collect_commit_contributors(
    #     self, token: str, repo: str, base: str, head: str, bot_blacklist=None
    # ) -> ContributionManager:
    #     if bot_blacklist is None:
    #         bot_blacklist = set()

    #     url = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
    #     headers = {"Authorization": f"token {token}"}
    #     r = requests.get(url, headers=headers)
    #     r.raise_for_status()
    #     data = r.json()
    #     commits = data.get("commits", [])

    #     contribution_manager = ContributionManager()
    #     coauthor_regex = re.compile(
    #         r"^Co-authored-by:\s*(.+?)\s*<(.+?)>$", re.IGNORECASE
    #     )

    #     for c in commits:
    #         sha = c.get("sha")
    #         commit_author = c.get("commit", {}).get("author", {})
    #         github_author = c.get("author")

    #         if github_author and github_author.get("login"):
    #             username = github_author["login"]
    #             if username not in bot_blacklist:
    #                 contributor = GitHubContributor(github_username=username)
    #                 contribution = CommitContribution(id=sha)
    #                 contribution_manager.add_contribution(contribution, contributor)
    #         elif commit_author:
    #             name = commit_author.get("name")
    #             if name in bot_blacklist:
    #                 continue
    #             email = commit_author.get("email")
    #             if name or email:
    #                 contributor = GitCommitContributor(
    #                     git_name=name.strip(), git_email=email.strip()
    #                 )
    #                 contribution = CommitContribution(id=sha)
    #                 contribution_manager.add_contribution(contribution, contributor)

    #         # add coauthors
    #         for line in c.get("commit", {}).get("message", "").splitlines():
    #             match = coauthor_regex.match(line.strip())
    #             if match:
    #                 name, email = match.groups()
    #                 if name not in bot_blacklist:
    #                     contributor = GitCommitContributor(
    #                         git_name=name.strip(), git_email=email.strip()
    #                     )
    #                     contribution = CommitContribution(id=sha)
    #                     contribution_manager.add_contribution(contribution, contributor)

    #     return contribution_manager

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

    #     def post_pull_request_comment(
    #         self,
    #         cff_file: CffFile,
    #         warnings: list,
    #         logs: list,
    #         token: str,
    #         repo: str,
    #         pr_number: str,
    #         contribution_details: dict,
    #         repo_for_compare: str,
    #         missing_authors: set,
    #         missing_author_invalidates_pr: bool,
    #         duplicate_authors: set,
    #         duplicate_author_invalidates_pr: bool,
    #     ):
    #         cff_path = cff_file.cff_path
    #         cff = cff_file.cff
    #         original_cff = cff_file.original_cff

    #         marker: str = "<!-- contributor-check-comment -->"
    #         timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    #         commit_sha = os.environ.get("GITHUB_SHA", "")
    #         commit_sha_short = commit_sha[:7]
    #         commit_url = f"https://github.com/{repo}/commit/{commit_sha}"

    #         # Add contribution details per new author
    #         comment_contributions = "\n**New Authors & Contributions:**\n"
    #         new_authors = contribution_details.keys() - {UNKNOWN_CONTRIBUTOR_KEY}
    #         if new_authors:
    #             for new_author in new_authors:
    #                 if new_author in missing_authors:
    #                     missing_author_message = f" (Missing from `{cff_path}`)"
    #                 else:
    #                     missing_author_message = ""
    #                 if isinstance(new_author, GitHubContributor):
    #                     # github user
    #                     comment_contributions += (
    #                         f"\n#### @{new_author}{missing_author_message}\n"
    #                     )
    #                 elif isinstance(new_author, GitCommitContributor):
    #                     # non github committer
    #                     new_author_name = new_author.git_name
    #                     new_author_email = new_author.git_email
    #                     if new_author_email:
    #                         comment_contributions += (
    #                             f"\n#### {new_author_email}{missing_author_message}\n"
    #                         )
    #                     else:
    #                         comment_contributions += (
    #                             f"\n#### {new_author_name}{missing_author_message}\n"
    #                         )
    #                 else:
    #                     raise Exception(
    #                         "Invalid new_author: It must be a GitHubContributor or a GitCommitContributor."
    #                     )

    #                 details = contribution_details.get(new_author, {})
    #                 for category, items in details.items():
    #                     comment_contributions += (
    #                         f"- **{category.replace('_', ' ').title()}**\n"
    #                     )
    #                     for item in items:
    #                         if category == "commits":
    #                             comment_contributions += f"  - [`{item[:7]}`](https://github.com/{repo_for_compare}/commit/{item})\n"
    #                         else:
    #                             comment_contributions += f"  - [Link]({item})\n"
    #         else:
    #             comment_contributions += "\n**No new authors.**\n"

    #         comment_body = f"""
    # {marker}
    # ### CFF Author Updater ###

    # {comment_contributions}
    # """
    #         if missing_authors:
    #             comment_body += f"""
    # **Recommended `{cff_path}` file (updated with missing authors):**
    # ```yaml
    # {yaml.dump(cff, sort_keys=False)}
    # ```
    # """
    #             comment_body += f"***Important: This recommended `{cff_path}` file has not been changed yet on this pull request. It can be manually copied and committed to the repository. For Github users to be recognized, you must use their Github user profile URL as their `alias` in the {cff_path} file."
    #             if missing_author_invalidates_pr:
    #                 comment_body += f" If the `{cff_path}` file is missing any new author, the pull request will remain invalid."
    #             comment_body += f"***"
    #         else:
    #             comment_body += f"""
    # **Current `{cff_path}` file contains all new authors.**
    # ```yaml
    # {yaml.dump(original_cff, sort_keys=False)}
    # ```
    # """
    #         if warnings:
    #             comment_body += "\n\n**Warnings:**\n" + "\n".join(warnings)

    #         if logs:
    #             comment_body += f"""

    # <details>
    # <summary><strong>ORCID Match Details</strong></summary>

    # {chr(10).join(logs)}

    # </details>"""

    #         comment_body += f"""

    # _Last updated: {timestamp} UTC · Commit [`{commit_sha_short}`]({commit_url})_

    # ***Powered by [CFF Author Updater v{self.github_action_version}](https://github.com/willynilly/cff-author-updater)***
    # """

    #         headers = {
    #             "Authorization": f"token {token}",
    #             "Accept": "application/vnd.github+json",
    #         }
    #         comments_url = (
    #             f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    #         )

    #         payload = {"body": comment_body}
    #         resp: requests.Response = requests.post(
    #             comments_url, headers=headers, json=payload
    #         )
    #         resp.raise_for_status()

    def post_pull_request_comment(
        self,
        cff_file: CffFile,
        warnings: list,
        logs: list,
        token: str,
        repo: str,
        pr_number: str,
        contribution_manager: ContributionManager,
        repo_for_compare: str,
        missing_authors: set,
        missing_author_invalidates_pr: bool,
        duplicate_authors: set,
        duplicate_author_invalidates_pr: bool,
    ):
        cff_path = cff_file.cff_path
        cff = cff_file.cff
        original_cff = cff_file.original_cff

        marker: str = "<!-- contributor-check-comment -->"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        commit_sha = os.environ.get("GITHUB_SHA", "")
        commit_sha_short = commit_sha[:7]
        commit_url = f"https://github.com/{repo}/commit/{commit_sha}"

        comment_contributions = "\n**New Authors & Contributions:**\n"

        new_authors = [
            contributor
            for contributor in contribution_manager.contributors_sorted_by_first_contribution
            if contributor in contribution_manager._contributions_by_contributor
        ]

        if new_authors:
            for contributor in new_authors:
                if contributor in missing_authors:
                    missing_author_message = f" (Missing from `{cff_path}`)"
                else:
                    missing_author_message = ""

                if isinstance(contributor, GitHubContributor):
                    comment_contributions += f"\n#### @{contributor.github_username}{missing_author_message}\n"
                elif isinstance(contributor, GitCommitContributor):
                    name = contributor.git_name
                    email = contributor.git_email
                    if email:
                        comment_contributions += (
                            f"\n#### {email}{missing_author_message}\n"
                        )
                    else:
                        comment_contributions += (
                            f"\n#### {name}{missing_author_message}\n"
                        )
                else:
                    raise Exception(
                        "Invalid contributor: Must be GitHubContributor or GitCommitContributor."
                    )

                contributions_by_category = (
                    contribution_manager.get_contribution_categories_for(contributor)
                )
                for category, contribution_list in contributions_by_category.items():
                    comment_contributions += (
                        f"- **{category.replace('_', ' ').title()}**\n"
                    )
                    for contribution in contribution_list:
                        if isinstance(
                            contribution, GitHubPullRequestCommitContribution
                        ):
                            comment_contributions += f"  - [`{contribution.id[:7]}`](https://github.com/{repo_for_compare}/commit/{contribution.id})\n"
                        else:
                            comment_contributions += f"  - [Link]({contribution.id})\n"
        else:
            comment_contributions += "\n**No new authors.**\n"

        # contributors = contribution_manager.contributors_sorted_by_first_contribution
        # if contributors:
        #     for contributor in contributors:
        #         if contributor in missing_authors:
        #             missing_author_message = f" (Missing from `{cff_path}`)"
        #         else:
        #             missing_author_message = ""

        #         if isinstance(contributor, GitHubContributor):
        #             comment_contributions += f"\n#### @{contributor.github_username}{missing_author_message}\n"
        #         elif isinstance(contributor, GitCommitContributor):
        #             name = contributor.git_name
        #             email = contributor.git_email
        #             if email:
        #                 comment_contributions += f"\n#### {email}{missing_author_message}\n"
        #             else:
        #                 comment_contributions += f"\n#### {name}{missing_author_message}\n"
        #         else:
        #             raise Exception(
        #                 "Invalid contributor: Must be GitHubContributor or GitCommitContributor."
        #             )

        #         contributions_by_category = contribution_manager.get_contribution_categories_for(contributor)
        #         for category, contribution_list in contributions_by_category.items():
        #             comment_contributions += f"- **{category.replace('_', ' ').title()}**\n"
        #             for contribution in contribution_list:
        #                 if isinstance(contribution, GitHubPullRequestCommitContribution):
        #                     comment_contributions += f"  - [`{contribution.id[:7]}`](https://github.com/{repo_for_compare}/commit/{contribution.id})\n"
        #                 else:
        #                     comment_contributions += f"  - [Link]({contribution.id})\n"
        # else:
        #     comment_contributions += "\n**No new authors.**\n"

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
            comment_body += (
                f"***Important: This recommended `{cff_path}` file has not been changed yet on this pull request. "
                f"It can be manually copied and committed to the repository. For Github users to be recognized, "
                f"you must use their Github user profile URL as their `alias` in the {cff_path} file."
            )
            if missing_author_invalidates_pr:
                comment_body += f" If the `{cff_path}` file is missing any new author, the pull request will remain invalid."
            comment_body += f"***"
        else:
            comment_body += f"""
**Current `{cff_path}` file contains all new authors.**
```yaml
{yaml.dump(original_cff, sort_keys=False)}
```
"""
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
