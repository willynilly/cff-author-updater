import logging
import os
import sys
from pathlib import Path

from cff_author_updater.flags import Flags
from cff_author_updater.logging_config import setup_logging
from cff_author_updater.managers.cff_manager import CffManager
from cff_author_updater.managers.contribution_manager import ContributionManager
from cff_author_updater.managers.github_pull_request_manager import (
    GitHubPullRequestManager,
)

# Set up logging
setup_logging()

logger = logging.getLogger(__name__)


def main():
    cff_path: Path = Path(os.environ.get("CFF_PATH", "CITATION.cff"))
    if not cff_path or not cff_path.exists():
        raise Exception(f"Invalid CFF_PATH env variable: `{cff_path}` does not exist.")

    github_pull_request_manager: GitHubPullRequestManager = GitHubPullRequestManager()
    cff_manager: CffManager = CffManager(
        cff_path=cff_path,
        github_pull_request_manager=github_pull_request_manager,
    )

    contribution_manager = ContributionManager()

    if Flags.has("authorship_for_pr_commits"):
        pr_commit_contribution_manager = (
            github_pull_request_manager.collect_contributors_for_pr_commits()
        )
        contribution_manager.merge(pr_commit_contribution_manager)

    if Flags.has("authorship_for_pr_reviews"):
        pr_review_contribution_manager = (
            github_pull_request_manager.collect_contributors_for_pr_reviews()
        )
        contribution_manager.merge(pr_review_contribution_manager)

    if Flags.has("authorship_for_pr_issues"):
        pr_issue_contribution_manager = (
            github_pull_request_manager.collect_contributors_for_pr_issues()
        )
        contribution_manager.merge(pr_issue_contribution_manager)

    if Flags.has("authorship_for_pr_issue_comments"):
        pr_issue_comment_contribution_manager = (
            github_pull_request_manager.collect_contributors_for_pr_issue_comments()
        )
        contribution_manager.merge(pr_issue_comment_contribution_manager)

    if Flags.has("authorship_for_pr_comments"):
        pr_comment_contribution_manager = (
            github_pull_request_manager.collect_contributors_for_pr_comments()
        )
        contribution_manager.merge(pr_comment_contribution_manager)

    missing_authors, duplicate_authors, cffconvert_validation_errors = (
        cff_manager.update_cff(contribution_manager=contribution_manager)
    )

    if Flags.has("missing_author_invalidates_pr") and len(missing_authors):
        sys.exit(1)
    if Flags.has("duplicate_author_invalidates_pr") and len(duplicate_authors):
        sys.exit(1)
    if Flags.has("invalid_cff_invalidates_pr") and len(cffconvert_validation_errors):
        sys.exit(1)


if __name__ == "__main__":
    main()
