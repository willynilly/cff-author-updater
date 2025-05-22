import os
import json

from managers.cff_manager import CffManager
from managers.github_manager import GithubManager
from managers.orcid_manager import OrcidManager


def main():
    repo: str = os.environ["REPO"]
    token: str = os.environ["GITHUB_TOKEN"]
    cff_path: str = os.environ.get("CFF_PATH", "CITATION.cff")
    output_file: str = os.environ.get("GITHUB_OUTPUT", "/tmp/github_output.txt")
    pr_number = None

    if os.path.exists(os.environ.get("GITHUB_EVENT_PATH", "")):
        with open(os.environ["GITHUB_EVENT_PATH"], "r") as f:
            event = json.load(f)
            pr_number = event.get("number") or event.get("pull_request", {}).get(
                "number"
            )
            if "pull_request" in event:
                head_repo = event["pull_request"]["head"]["repo"]["full_name"]
                head_branch = event["pull_request"]["head"]["ref"]
                base_branch = event["pull_request"]["base"]["ref"]
                repo_for_compare = head_repo
            else:
                print("This workflow only supports pull_request events.")
                return
    else:
        print("GITHUB_EVENT_PATH is missing.")
        return

    flags: dict = {
        "commits": os.environ.get("AUTHORSHIP_FOR_PR_COMMITS", "true").casefold()
        == "true",
        "reviews": os.environ.get("AUTHORSHIP_FOR_PR_REVIEWS", "true").casefold()
        == "true",
        "issues": os.environ.get("AUTHORSHIP_FOR_PR_ISSUES", "true").casefold()
        == "true",
        "issue_comments": os.environ.get(
            "AUTHORSHIP_FOR_PR_ISSUE_COMMENTS", "true"
        ).casefold()
        == "true",
        "pr_comments": os.environ.get("AUTHORSHIP_FOR_PR_COMMENT", "true").casefold()
        == "true",
        "include_coauthors": os.environ.get("INCLUDE_COAUTHORS", "true").casefold()
        == "true",
        "post_comment": os.environ.get("POST_COMMENT", "true").casefold() == "true",
    }

    orcid_manager = OrcidManager()
    github_manager = GithubManager()
    cff_manager = CffManager(orcid_manager=orcid_manager, github_manager=github_manager)

    contributors: set = set()
    metadata: dict = {}
    if flags["commits"]:
        commit_contributors, metadata = github_manager.collect_commit_contributors(
            token=token,
            repo=repo_for_compare,
            base=base_branch,
            head=head_branch,
            include_coauthors=flags["include_coauthors"],
        )
        contributors = set(commit_contributors)

    if pr_number:
        metadata_flags = {
            "authorship_for_pr_reviews": flags["reviews"],
            "authorship_for_pr_issues": flags["issues"],
            "authorship_for_pr_issue_comments": flags["issue_comments"],
            "authorship_for_pr_comment": flags["pr_comments"],
        }
        contributors.update(
            github_manager.collect_metadata_contributors(
                token, repo, pr_number, metadata_flags
            )
        )
        cff_manager.process_contributors(
            contributors=contributors,
            cff_path=cff_path,
            token=token,
            repo=repo,
            pr_number=pr_number,
            output_file=output_file,
            flags=flags,
            contributor_metadata=metadata,
        )


if __name__ == "__main__":
    main()
