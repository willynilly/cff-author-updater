import os
import json
from pathlib import Path
import sys

from flags import Flags

from src.managers.cff_manager import CffManager
from src.managers.github_manager import GithubManager
from src.managers.orcid_manager import OrcidManager
from src.utils import add_more_contribution_details


def main():
    bot_blacklist = set(
        os.environ.get("BOT_BLACKLIST", "github-actions[bot]").split(",")
    )
    repo: str = os.environ["REPO"]
    token: str = os.environ["GITHUB_TOKEN"]
    cff_path: Path = Path(os.environ.get("CFF_PATH", "CITATION.cff"))
    output_file: str = os.environ.get("GITHUB_OUTPUT", "/tmp/github_output.txt")
    pr_number = None
    github_event_path: Path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))

    if not cff_path or not cff_path.exists():
        raise Exception(f"Invalid CFF_PATH env variable: `{cff_path}` does not exist.")

    if github_event_path and github_event_path.exists():
        with open(github_event_path, "r") as f:
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
                raise Exception("This workflow only supports pull_request events.")
    else:
        raise Exception("GITHUB_EVENT_PATH is missing.")

    orcid_manager: OrcidManager = OrcidManager()
    github_manager: GithubManager = GithubManager()
    cff_manager: CffManager = CffManager(
        cff_path=cff_path, orcid_manager=orcid_manager, github_manager=github_manager
    )

    contributors: set = set()
    contribution_details: dict = {}
    if Flags.has("authorship_for_pr_commits"):
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

        collected_contributors, more_contribution_details = (
            github_manager.collect_metadata_contributors(
                token=token,
                repo=repo,
                pr_number=pr_number,
                bot_blacklist=bot_blacklist,
            )
        )

        contributors.update(collected_contributors)
        add_more_contribution_details(
            contribution_details=contribution_details,
            more_contribution_details=more_contribution_details,
        )

        missing_authors = cff_manager.update_cff(
            contributors=contributors,
            token=token,
            repo=repo,
            pr_number=pr_number,
            output_file=output_file,
            repo_for_compare=repo_for_compare,
            contribution_details=contribution_details,
        )

        if len(contributors):
            print(
                f"The `{cff_path}` file has been updated with {len(contributors)} new authors."
            )
            if Flags.has("missing_author_invalidates_pr") and len(missing_authors):
                print(
                    f"Pull request is invalidated because a new author is missing from the `{cff_path}` file."
                )
                sys.exit(1)


if __name__ == "__main__":
    main()
