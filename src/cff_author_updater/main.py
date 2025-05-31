import os
import json
from pathlib import Path
import sys

from cff_author_updater.flags import Flags

from cff_author_updater.managers.cff_manager import CffManager
from cff_author_updater.managers.github_manager import GithubManager
from cff_author_updater.managers.orcid_manager import OrcidManager
from cff_author_updater.managers.contribution_manager import ContributionManager


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

    contribution_manager = ContributionManager()

    if Flags.has("authorship_for_pr_commits"):
        commit_contribution_manager = github_manager.collect_commit_contributors(
            token=token,
            repo=repo_for_compare,
            base=base_branch,
            head=head_branch,
            bot_blacklist=bot_blacklist,
        )
        contribution_manager.merge(commit_contribution_manager)

    if pr_number:
        metadata_contribution_manager = github_manager.collect_metadata_contributors(
            token=token,
            repo=repo,
            pr_number=pr_number,
            bot_blacklist=bot_blacklist,
        )
        contribution_manager.merge(metadata_contribution_manager)

        missing_authors, duplicate_authors, cffconvert_validation_errors = (
            cff_manager.update_cff(
                token=token,
                repo=repo,
                pr_number=pr_number,
                output_file=output_file,
                repo_for_compare=repo_for_compare,
                contribution_manager=contribution_manager,
            )
        )

        new_authors_count = len(contribution_manager.contributors)
        if new_authors_count > 0:
            print(
                f"The `{cff_path}` file has been updated with {new_authors_count} new authors."
            )
            if Flags.has("missing_author_invalidates_pr") and len(missing_authors):
                print(
                    f"Pull request is invalidated because a new author is missing from the `{cff_path}` file."
                )
                sys.exit(1)
        if Flags.has("duplicate_author_invalidates_pr") and len(duplicate_authors):
            print(
                f"Pull request is invalidated because there is a duplicate author in the `{cff_path}` file."
            )
            sys.exit(1)
        if Flags.has("invalid_cff_invalidates_pr") and len(
            cffconvert_validation_errors
        ):
            print(
                f"Pull request is invalidated because the `{cff_path}` file is not valid CFF."
            )
            print("\n".join(cffconvert_validation_errors))
            sys.exit(1)


if __name__ == "__main__":
    main()
