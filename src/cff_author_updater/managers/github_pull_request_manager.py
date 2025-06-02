import os
import re
from datetime import datetime

import requests

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
from cff_author_updater.contributors.cff_author_contributor import CffAuthorContributor
from cff_author_updater.contributors.contributor import Contributor
from cff_author_updater.contributors.git_commit_contributor import GitCommitContributor
from cff_author_updater.contributors.github_contributor import (
    GitHubContributor,
)
from cff_author_updater.flags import Flags
from cff_author_updater.managers.contribution_manager import ContributionManager
from cff_author_updater.managers.github_manager import GitHubManager

UNKNOWN_CONTRIBUTOR_KEY = ("unknown", None)
DEFAULT_GITHUB_ACTION_BOT = "github-actions[bot]"


class GitHubPullRequestManager(GitHubManager):

    def __init__(self):
        super().__init__()

    def _load_from_environment_variables(self):
        super()._load_from_environment_variables()

        self.bot_blacklist = set(
            os.environ.get("BOT_BLACKLIST", DEFAULT_GITHUB_ACTION_BOT).split(",")
        )

        if len(self.bot_blacklist) == 0:
            raise Exception(
                "BOT_BLACKLIST environment variable is empty. Please set it to a comma-separated list of bot usernames."
            )

    def _load_github_event(self, event: dict):
        super()._load_github_event(event=event)
        self.pr_number = str(event.get("number")) or str(event.get("pull_request", {}).get(
            "number"
        ))

        if not isinstance(self.pr_number, str):
            raise Exception(
                f"Cannot load github event: pr_number must be a string: {self.pr_number}"
            )

        if "pull_request" in event:
            self.head_repo = event["pull_request"]["head"]["repo"]["full_name"]
            self.head_branch = event["pull_request"]["head"]["ref"]
            self.base_branch = event["pull_request"]["base"]["ref"]
            self.repo_for_compare = self.head_repo
        else:
            raise Exception(
                "GitHubPullRequestManager only supports pull_request events."
            )

    # def get_linked_issues(self, session: requests.Session, repo: str, pr_number: str):
    #     url: str = f"https://api.github.com/repos/{repo}/issues/{pr_number}/timeline"
    #     headers: dict = {"Accept": "application/vnd.github.mockingbird-preview+json"}
    #     response: requests.Response = session.get(url, headers=headers)
    #     if response.status_code != 200:
    #         return []
    #     data = response.json()
    #     return [
    #         event["source"]["issue"]["number"]
    #         for event in data
    #         if event.get("event") == "cross-referenced"
    #         and event.get("source", {}).get("issue", {}).get("pull_request") is None
    #     ]

    def collect_contributors_for_pr_reviews(self) -> ContributionManager:
        contribution_manager = ContributionManager()

        # PR Reviews
        if Flags.has("authorship_for_pr_reviews"):

            token = self.token
            repo = self.repo
            pr_number = self.pr_number
            bot_blacklist = self.bot_blacklist

            session: requests.Session = self.get_github_session(token=token)

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

        return contribution_manager

    def collect_contributors_for_pr_comments(self) -> ContributionManager:
        contribution_manager = ContributionManager()

        # PR Comments
        if Flags.has("authorship_for_pr_comments"):
            token = self.token
            repo = self.repo
            pr_number = self.pr_number
            bot_blacklist = self.bot_blacklist

            session: requests.Session = self.get_github_session(token=token)

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

        return contribution_manager

    # def collect_contributors_for_pr_issues(self) -> ContributionManager:
    #     contribution_manager = ContributionManager()

    #     # PR Issues
    #     if Flags.has("authorship_for_pr_issues"):
    #         token = self.token
    #         repo = self.repo
    #         pr_number = self.pr_number
    #         bot_blacklist = self.bot_blacklist

    #         session: requests.Session = self.get_github_session(token=token)

    #         linked_issues = self.get_linked_issues(
    #             session=session, repo=repo, pr_number=pr_number
    #         )
    #         for issue_number in linked_issues:

    #             issue_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    #             issue = session.get(issue_url).json()
    #             github_username = issue.get("user", {}).get("login")
    #             url = issue.get("html_url")
    #             created_at_str = issue.get("created_at")
    #             created_at = (
    #                 datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
    #                 if created_at_str
    #                 else datetime.min
    #             )
    #             if github_username and github_username not in bot_blacklist:
    #                 contributor = GitHubContributor(github_username=github_username)
    #                 contribution = GitHubPullRequestIssueContribution(
    #                     id=url, created_at=created_at
    #                 )
    #                 contribution_manager.add_contribution(contribution, contributor)

    #     return contribution_manager

    def collect_contributors_for_pr_issues(self) -> ContributionManager:
        contribution_manager = ContributionManager()

        if Flags.has("authorship_for_pr_issues"):

            bot_blacklist = self.bot_blacklist

            linked_issues = self.get_linked_issues_graphql()

            for issue in linked_issues:
                github_username = issue["author"]["login"] if issue["author"] else None
                url = issue["url"]
                created_at_str = issue["createdAt"]
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

        return contribution_manager


    # def collect_contributors_for_pr_issue_comments(self):
    #     contribution_manager = ContributionManager()

    #     # PR Issue Comments
    #     if Flags.has("authorship_for_pr_issue_comments"):

    #         token = self.token
    #         repo = self.repo
    #         pr_number = self.pr_number
    #         bot_blacklist = self.bot_blacklist

    #         session: requests.Session = self.get_github_session(token=token)

    #         linked_issues = self.get_linked_issues(
    #             session=session, repo=repo, pr_number=pr_number
    #         )
    #         for issue_number in linked_issues:

    #             comments_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    #             for comment in session.get(comments_url).json():
    #                 github_username = comment.get("user", {}).get("login")
    #                 url = comment.get("html_url")
    #                 created_at_str = comment.get("created_at")
    #                 created_at = (
    #                     datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
    #                     if created_at_str
    #                     else datetime.min
    #                 )
    #                 if github_username and github_username not in bot_blacklist:
    #                     contributor = GitHubContributor(github_username=github_username)
    #                     contribution = GitHubPullRequestIssueCommentContribution(
    #                         id=url, created_at=created_at
    #                     )
    #                     contribution_manager.add_contribution(contribution, contributor)

    #     return contribution_manager

    def collect_contributors_for_pr_issue_comments(self) -> ContributionManager:
        contribution_manager = ContributionManager()

        if Flags.has("authorship_for_pr_issue_comments"):

            token = self.token
            repo = self.repo
            bot_blacklist = self.bot_blacklist

            session: requests.Session = self.get_github_session(token=token)

            linked_issues = self.get_linked_issues_graphql()

            for issue in linked_issues:
                issue_number = issue["number"]

                comments_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
                response = session.get(comments_url)
                response.raise_for_status()

                comments = response.json()
                for comment in comments:
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
                        contribution = GitHubPullRequestIssueCommentContribution(
                            id=url, created_at=created_at
                        )
                        contribution_manager.add_contribution(contribution, contributor)

        return contribution_manager

    
    def get_linked_issues_graphql(self) -> list[dict]:
        token = self.token
        repo_owner, repo_name = self.repo.split("/")
        pr_number = int(self.pr_number)

        url = "https://api.github.com/graphql"
        headers = {
            "Authorization": f"bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        query = """
        query($owner: String!, $name: String!, $prNumber: Int!) {
        repository(owner: $owner, name: $name) {
            pullRequest(number: $prNumber) {
            closingIssuesReferences(first: 50) {
                nodes {
                number
                url
                author {
                    login
                }
                createdAt
                }
            }
            }
        }
        }
        """

        variables = {
            "owner": repo_owner,
            "name": repo_name,
            "prNumber": pr_number,
        }

        response = requests.post(
            url, json={"query": query, "variables": variables}, headers=headers
        )
        response.raise_for_status()
        data = response.json()

        issues = data.get("data", {}).get("repository", {}).get("pullRequest", {}).get("closingIssuesReferences", {}).get("nodes", [])

        return issues


    # def collect_contributors_for_pr_commits(self) -> ContributionManager:
    #     contribution_manager = ContributionManager()

    #     # PR Commits
    #     if Flags.has("authorship_for_pr_commits"):

    #         token = self.token
    #         repo = self.repo
    #         base = self.base_branch
    #         head = self.head_branch
    #         bot_blacklist = self.bot_blacklist

    #         url = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
    #         headers = {"Authorization": f"token {token}"}
    #         r = requests.get(url, headers=headers)
    #         r.raise_for_status()
    #         data = r.json()
    #         commits = data.get("commits", [])

    #         coauthor_regex = re.compile(
    #             r"^Co-authored-by:\s*(.+?)\s*<(.+?)>$", re.IGNORECASE
    #         )

    #         for c in commits:
    #             sha = c.get("sha")
    #             commit_author_data = c.get("commit", {}).get("author", {})
    #             github_author = c.get("author")

    #             commit_date_str = commit_author_data.get("date")
    #             commit_date = (
    #                 datetime.strptime(commit_date_str, "%Y-%m-%dT%H:%M:%SZ")
    #                 if commit_date_str
    #                 else datetime.min
    #             )

    #             if github_author and github_author.get("login"):
    #                 username = github_author["login"]
    #                 if username not in bot_blacklist:
    #                     contributor = GitHubContributor(github_username=username)
    #                     contribution = GitHubPullRequestCommitContribution(
    #                         sha=sha, created_at=commit_date
    #                     )
    #                     contribution_manager.add_contribution(contribution, contributor)
    #             elif commit_author_data:
    #                 name = commit_author_data.get("name")
    #                 if name in bot_blacklist:
    #                     continue
    #                 email = commit_author_data.get("email")
    #                 if name or email:
    #                     contributor = GitCommitContributor(
    #                         git_name=name.strip(), git_email=email.strip()
    #                     )
    #                     contribution = GitHubPullRequestCommitContribution(
    #                         sha=sha, created_at=commit_date
    #                     )
    #                     contribution_manager.add_contribution(contribution, contributor)

    #             # add coauthors
    #             for line in c.get("commit", {}).get("message", "").splitlines():
    #                 match = coauthor_regex.match(line.strip())
    #                 if match:
    #                     name, email = match.groups()
    #                     if name not in bot_blacklist:
    #                         contributor = GitCommitContributor(
    #                             git_name=name.strip(), git_email=email.strip()
    #                         )
    #                         contribution = GitHubPullRequestCommitContribution(
    #                             sha=sha, created_at=commit_date
    #                         )
    #                         contribution_manager.add_contribution(
    #                             contribution, contributor
    #                         )

    #     return contribution_manager

    def collect_contributors_for_pr_commits(self) -> ContributionManager:
        contribution_manager = ContributionManager()

        if Flags.has("authorship_for_pr_commits"):

            token = self.token
            repo = self.repo
            pr_number = self.pr_number
            bot_blacklist = self.bot_blacklist

            session: requests.Session = self.get_github_session(token=token)

            url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/commits"
            r = session.get(url)
            r.raise_for_status()
            commits = r.json()

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
                            contribution_manager.add_contribution(
                                contribution, contributor
                            )

        return contribution_manager

    def scan_pr_comments_for_skip_commands(self) -> dict[str, set[str]]:
        """
        Scans PR comments for skip-authorship and unskip-authorship commands.

        Returns final skip state:
        {
            "orcid": set(),
            "name": set(),
            "email": set(),
            "github-username": set(),
        }
        """
        token = self.token
        repo = self.repo
        pr_number = self.pr_number

        session: requests.Session = self.get_github_session(token=token)

        comments_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        response = session.get(comments_url)
        response.raise_for_status()

        comments = response.json()

        # Initialize state tracking — value → skip=True/False
        skip_state = {
            "orcid": {},
            "name": {},
            "email": {},
            "github-username": {},
        }
        

        # Sort comments oldest → newest by created_at
        comments_sorted = sorted(comments, key=lambda c: c["created_at"])

        for comment in comments_sorted:
            body = comment.get("body", "")
            for line in body.splitlines():
                line = line.strip()

                if line.startswith("skip-authorship-by-orcid"):
                    value = line[len("skip-authorship-by-orcid"):].strip()
                    skip_state["orcid"][value] = True

                elif line.startswith("unskip-authorship-by-orcid"):
                    value = line[len("unskip-authorship-by-orcid"):].strip()
                    skip_state["orcid"][value] = False

                elif line.startswith("skip-authorship-by-name"):
                    value = line[len("skip-authorship-by-name"):].strip()
                    skip_state["name"][value] = True

                elif line.startswith("unskip-authorship-by-name"):
                    value = line[len("unskip-authorship-by-name"):].strip()
                    skip_state["name"][value] = False

                elif line.startswith("skip-authorship-by-email"):
                    value = line[len("skip-authorship-by-email"):].strip()
                    skip_state["email"][value] = True

                elif line.startswith("unskip-authorship-by-email"):
                    value = line[len("unskip-authorship-by-email"):].strip()
                    skip_state["email"][value] = False

                elif line.startswith("skip-authorship-by-github-username"):
                    value = line[len("skip-authorship-by-github-username"):].strip()
                    skip_state["github-username"][value] = True

                elif line.startswith("unskip-authorship-by-github-username"):
                    value = line[len("unskip-authorship-by-github-username"):].strip()
                    skip_state["github-username"][value] = False

        # Final skip state — only values where latest command is skip=True
        final_skips = {
            field: set(value for value, skip in skip_state[field].items() if skip)
            for field in skip_state
        }

        return final_skips

    def should_skip_contributor(self, contributor: Contributor, skip_commands: dict[str, set[str]]) -> bool:
        """
        Returns True if this contributor should be skipped based on skip_commands.
        """

        if not Flags.has("can_skip_authorship"):
            return False

        if isinstance(contributor, GitHubContributor):
            if contributor.github_username in skip_commands["github-username"]:
                return True
            
        if isinstance(contributor, GitCommitContributor):
            if contributor.git_email in skip_commands["email"]:
                return True
            if contributor.git_name in skip_commands["name"]:
                return True
            
        if isinstance(contributor, CffAuthorContributor):
            if contributor.cff_author_data.get('alias', '') in skip_commands["orcid"]:
                return True
            if contributor.cff_author_data.get('email', '') in skip_commands["email"]:
                return True
            if contributor.cff_author_data.get('name', '') in skip_commands["name"]:
                return True
            full_name:str = contributor.cff_author_data.get('given-names', '') + ' ' + contributor.cff_author_data.get('family-names', '')
            if full_name in skip_commands["name"]:
                return True
            

        # if isinstance(contributor, GitCommitContributor):
        #     github_username = None
        #     if contributor.git_alias:
        #         github_username = parse_github_username_from_github_profile_url(url=contributor.git_alias)
        #     if github_username and github_username in skip_commands["github-username"]:
        #         return True




        # Example: if you add ORCID field later:
        # if hasattr(contributor, "orcid"):
        #     if contributor.orcid in skip_commands["orcid"]:
        #         return True

        return False


    def post_pull_request_comment(self, comment_body: str):
        if Flags.has("post_pr_comment"):
            token = self.token
            repo = self.repo
            pr_number = self.pr_number

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
