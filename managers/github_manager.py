import os
import re
import requests
import yaml


class GithubManager:

    def __init__(self):
        pass

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
        self, token: str, repo: str, pr_number: str, flags: dict
    ) -> set:
        session: requests.Session = self.get_github_session(token=token)
        contributors: set = set()

        if flags.get("authorship_for_pr_reviews"):
            reviews_url = (
                f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
            )
            for review in session.get(reviews_url).json():
                user = review.get("user", {}).get("login")
                if user:
                    contributors.add(user)

        if flags.get("authorship_for_pr_comment"):
            comments_url: str = (
                f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            )
            for comment in session.get(comments_url).json():
                user = comment.get("user", {}).get("login")
                if user:
                    contributors.add(user)

        if flags.get("authorship_for_pr_issues") or flags.get(
            "authorship_for_pr_issue_comments"
        ):
            linked_issues = self.get_linked_issues(
                session=session, repo=repo, pr_number=pr_number
            )
            for issue_number in linked_issues:
                if flags.get("authorship_for_pr_issues"):
                    issue_url: str = (
                        f"https://api.github.com/repos/{repo}/issues/{issue_number}"
                    )
                    issue = session.get(issue_url).json()
                    author = issue.get("user", {}).get("login")
                    if author:
                        contributors.add(author)

                if flags.get("authorship_for_pr_issue_comments"):
                    comments_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
                    for comment in session.get(comments_url).json():
                        user = comment.get("user", {}).get("login")
                        if user:
                            contributors.add(user)

        return contributors

    def collect_commit_contributors(
        self,
        token: str,
        repo: str,
        base: str,
        head: str,
        include_coauthors: bool = True,
    ):
        url: str = f"https://api.github.com/repos/{repo}/compare/{base}...{head}"
        headers: dict = {"Authorization": f"token {token}"}
        r: requests.Response = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        commits: list = data.get("commits", [])
        contributors = set()
        contributor_metadata: dict = {}
        coauthor_regex = re.compile(
            r"^Co-authored-by:\s*(.+?)\s*<(.+?)>$", re.IGNORECASE
        )

        for c in commits:
            sha: str = c.get("sha")
            commit_author = c.get("commit", {}).get("author", {})
            github_author = c.get("author")

            if github_author and github_author.get("login"):
                contributors.add(github_author["login"])
                contributor_metadata[github_author["login"]] = {"sha": sha}
            elif commit_author:
                name = commit_author.get("name")
                email = commit_author.get("email")
                key = (name, email)
                if name or email:
                    contributors.add(key)
                    contributor_metadata[key] = {"sha": sha}
                else:
                    contributor_metadata[("unknown", None)] = {"sha": sha}

            if include_coauthors:
                for line in c.get("commit", {}).get("message", "").splitlines():
                    match = coauthor_regex.match(line.strip())
                    if match:
                        name, email = match.groups()
                        key = (name.strip(), email.strip())
                        contributors.add(key)
                        contributor_metadata[key] = {"sha": sha}

        return sorted(contributors), contributor_metadata

    def post_pull_request_comment(
        self,
        new_users: list,
        cff_path: str,
        cff: dict,
        warnings: list,
        logs: list,
        token: str,
        repo: str,
        pr_number: str,
    ):

        marker: str = "<!-- contributor-check-comment -->"
        timestamp = (
            requests.get("https://timeapi.io/api/Time/current/zone?timeZone=UTC")
            .json()
            .get("dateTime", "")[:16]
            .replace("T", " ")
        )
        commit_sha = os.environ.get("GITHUB_SHA", "")[:7]
        comment_body = f"""
{marker}
### New Authors Detected

**New GitHub Users or Commit Authors:**
{chr(10).join(f"- {u}" for u in new_users) if new_users else "_None_"}

**Updated `{cff_path}` file:**
```yaml
{yaml.dump(cff, sort_keys=False)}
```
"""

        if warnings:
            comment_body += "\n**Warnings & Recommendations:**\n" + "\n".join(warnings)

        if logs:
            comment_body += f"""

    <details>
    <summary><strong>ORCID Match Details</strong></summary>

    {chr(10).join(logs)}

    </details>"""

        comment_body += f"""

    _Last updated: {timestamp} UTC · Commit `{commit_sha}`_
    """

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        }
        comments_url = (
            f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        )
        existing = requests.get(comments_url, headers=headers).json()
        existing_comment = next(
            (c for c in existing if marker in c.get("body", "")), None
        )

        payload = {"body": comment_body}
        if existing_comment:
            comment_id = existing_comment["id"]
            print("posting to existing PR comment")
            print("url", f"{comments_url}/{comment_id}")
            print("headers", headers)
            print("payload", payload)
            resp: requests.Response = requests.patch(
                f"{comments_url}/{comment_id}", headers=headers, json=payload
            )
            resp.raise_for_status()
        else:
            print("posting new PR comment")
            print("url", comments_url)
            print("headers", headers)
            print("payload", payload)
            resp: requests.Response = requests.post(
                comments_url, headers=headers, json=payload
            )
            resp.raise_for_status()
