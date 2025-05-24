import os
import json
import sys

from managers.cff_manager import CffManager
from managers.github_manager import GithubManager
from managers.orcid_manager import OrcidManager
from utils import add_more_contribution_details


def main():
    bot_blacklist = set(
        os.environ.get("BOT_BLACKLIST", "github-actions[bot]").split(",")
    )
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
        "post_comment": os.environ.get("POST_COMMENT", "true").casefold() == "true",
        "new_author_invalidates_pr": os.environ.get(
            "NEW_AUTHOR_INVALIDATES_PR", "true"
        ).casefold()
        == "true",
    }

    orcid_manager = OrcidManager()
    github_manager = GithubManager()
    cff_manager = CffManager(orcid_manager=orcid_manager, github_manager=github_manager)

    contributors: set = set()
    contribution_details: dict = {}
    if flags["commits"]:
        commit_contributors, more_contribution_details = (
            github_manager.collect_commit_contributors(
                token=token,
                repo=repo_for_compare,
                base=base_branch,
                head=head_branch,
                bot_blacklist=bot_blacklist,
            )
        )
        contributors = set(commit_contributors)
        add_more_contribution_details(
            contribution_details=contribution_details,
            more_contribution_details=more_contribution_details,
        )

    if pr_number:
        metadata_flags = {
            "authorship_for_pr_reviews": flags["reviews"],
            "authorship_for_pr_issues": flags["issues"],
            "authorship_for_pr_issue_comments": flags["issue_comments"],
            "authorship_for_pr_comment": flags["pr_comments"],
        }

        collected_contributors, more_contribution_details = (
            github_manager.collect_metadata_contributors(
                token=token,
                repo=repo,
                pr_number=pr_number,
                flags=metadata_flags,
                bot_blacklist=bot_blacklist,
            )
        )

        contributors.update(collected_contributors)
        add_more_contribution_details(
            contribution_details=contribution_details,
            more_contribution_details=more_contribution_details,
        )

        cff_manager.process_contributors(
            contributors=contributors,
            cff_path=cff_path,
            token=token,
            repo=repo,
            pr_number=pr_number,
            output_file=output_file,
            flags=flags,
            repo_for_compare=repo_for_compare,
            contribution_details=contribution_details,
        )

        if len(contributors):
            print(
                f"The `{cff_path}` file has been updated with {len(contributors)} new authors."
            )
            if flags["new_author_invalidates_pr"]:
                print("Pull request is invalidated due to new author.")
                sys.exit(1)


if __name__ == "__main__":
    main()
