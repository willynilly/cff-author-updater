import logging
import os
import sys
from pathlib import Path

from cff_author_updater.contributors.git_commit_contributor import GitCommitContributor
from cff_author_updater.contributors.github_contributor import GitHubContributor
from cff_author_updater.flags import Flags
from cff_author_updater.logging_config import setup_logging
from cff_author_updater.managers.cff_manager import CffManager
from cff_author_updater.managers.contribution_manager import ContributionManager
from cff_author_updater.managers.github_pull_request_manager import (
    GitHubPullRequestManager,
)
from cff_author_updater.managers.orcid_manager import OrcidManager

# Set up logging
setup_logging()

logger = logging.getLogger(__name__)


def main():
    cff_path: Path = Path(os.environ.get("CFF_PATH", "CITATION.cff"))
    if not cff_path or not cff_path.exists():
        raise Exception(f"Invalid CFF_PATH env variable: `{cff_path}` does not exist.")

    orcid_manager: OrcidManager = OrcidManager()
    github_pull_request_manager: GitHubPullRequestManager = GitHubPullRequestManager()
    cff_manager: CffManager = CffManager(
        cff_path=cff_path,
        orcid_manager=orcid_manager,
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

    new_authors_count = len(contribution_manager.contributors)
    if new_authors_count > 0:
        logger.info(
            f"The `{cff_path}` file has been updated with {new_authors_count} new authors."
        )
        

        if Flags.has("missing_author_invalidates_pr") and len(missing_authors):
            logger.error(
                f"Pull request is invalidated because {len(missing_authors)} new author(s) are missing from the `{cff_path}` file."
            )

            for contributor in missing_authors:
                identifier = cff_manager.create_identifier_of_contributor_for_logger(contributor)
                
                reason = ""
                
                if isinstance(contributor, GitHubContributor):
                    reason = (
                        f"unmatched CFF author — possible cause: existing `{cff_path}` entry is missing an 'alias' with this GitHub profile URL: "
                        f"{contributor.github_user_profile_url}"
                    )
                
                elif isinstance(contributor, GitCommitContributor):
                    reasons = []
                    if not contributor.git_name:
                        reasons.append("missing commit name")
                    if not contributor.git_email:
                        reasons.append("missing commit email")
                    if reasons:
                        reason = "cannot generate CFF author (" + "; ".join(reasons) + ")"
                    else:
                        reason = "unmatched CFF author (possible formatting mismatch)"
                
                else:
                    reason = "unknown contributor type"
                
                logger.error(f"Missing author: {identifier} — {reason}")
            
            sys.exit(1)

    if Flags.has("duplicate_author_invalidates_pr") and len(duplicate_authors):
        logger.error(
            f"Pull request is invalidated because there is a duplicate author in the `{cff_path}` file."
        )
        sys.exit(1)
    if Flags.has("invalid_cff_invalidates_pr") and len(cffconvert_validation_errors):
        logger.error(
            f"Pull request is invalidated because the `{cff_path}` file is not valid CFF.\n"
            + "\n".join(cffconvert_validation_errors)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
