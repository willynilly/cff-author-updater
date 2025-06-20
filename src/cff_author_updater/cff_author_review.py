import logging
import os
from datetime import datetime, timezone

import regex
import yaml

from cff_author_updater.cff_file import CffFile
from cff_author_updater.contributions.github_pull_request_commit_contribution import (
    GitHubPullRequestCommitContribution,
)
from cff_author_updater.contributors.contributor import Contributor
from cff_author_updater.contributors.git_commit_contributor import GitCommitContributor
from cff_author_updater.contributors.github_contributor import GitHubContributor
from cff_author_updater.flags import Flags
from cff_author_updater.logging_config import get_log_collector
from cff_author_updater.managers.contribution_manager import ContributionManager
from cff_author_updater.managers.github_pull_request_manager import (
    GitHubPullRequestManager,
)

logger = logging.getLogger(__name__)


class CffAuthorReview:

    def __init__(
        self,
        cff_file: CffFile,
        github_pull_request_manager: GitHubPullRequestManager,
        contribution_manager: ContributionManager,
        contributors_skipped_for_authorship: set[Contributor],
        missing_authors: set[Contributor],
        missing_author_invalidates_pr: bool,
        duplicate_authors: set,
        duplicate_author_invalidates_pr: bool,
        cffconvert_validation_errors: list[str]
    ):
        self.cff_file = cff_file
        self.github_pull_request_manager = github_pull_request_manager
        self.repo = self.github_pull_request_manager.repo
        self.pr_number = self.github_pull_request_manager.pr_number
        self.github_action_version = self.github_pull_request_manager.github_action_version
        self.repo_for_compare = self.github_pull_request_manager.repo_for_compare
        self.contribution_manager = contribution_manager
        self.contributors_skipped_for_authorship = contributors_skipped_for_authorship
        self.missing_authors = missing_authors
        self.missing_author_invalidates_pr = missing_author_invalidates_pr
        self.duplicate_authors = duplicate_authors
        self.duplicate_author_invalidates_pr = duplicate_author_invalidates_pr
        self.cffconvert_validation_errors = cffconvert_validation_errors

  
    def _split_pascal_case(self, text: str) -> str:
        """
        Splits a PascalCase string into words, Unicode-friendly.
        """
        return regex.sub(r"(?<!^)(?=\p{Lu})", " ", text)


    def get_review(self) -> str:

        cff_path = self.cff_file.cff_path
        cff = self.cff_file.cff
        original_cff = self.cff_file.original_cff

        log_collector = get_log_collector()
        error_logs = log_collector.get_error_logs(is_unique=True)
        warning_logs = log_collector.get_warning_logs(is_unique=True)
        info_logs = log_collector.get_info_logs(is_unique=True)

        marker: str = "<!-- cff-author-updater-pr-comment -->"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        commit_sha = os.environ.get("GITHUB_SHA", "")
        commit_sha_short = commit_sha[:7]
        commit_url = f"https://github.com/{self.repo}/commit/{commit_sha}"

        body_pr_validation_status_value: str = ""
        if len(error_logs) > 0:
            if len(warning_logs) > 0:
                body_pr_validation_status_value = "Invalid (with Errors and Warnings)"
            else:
                body_pr_validation_status_value = "Invalid (with Errors)"
        else:
            if len(warning_logs) > 0:
                body_pr_validation_status_value = "Valid (with Warnings)"
            else:
                body_pr_validation_status_value = "Valid"
        body_pr_validation_status = (
            f"\n**Pull Request Status: {body_pr_validation_status_value}**\n"
        )

        body_contributions = "\n**Contributors & Contributions in Pull Request:**\n"

        contributors_in_pr = [
            contributor
            for contributor in self.contribution_manager.contributors_sorted_by_first_contribution
        ]


        if contributors_in_pr:
            for contributor in contributors_in_pr:
                if contributor in self.missing_authors:
                    missing_author_message = f" (Missing author from `{cff_path}`)"
                else:
                    missing_author_message = ""

                if contributor in self.contributors_skipped_for_authorship:
                    skipped_for_authorship_message = " (Skipped for recommended or required authorship)"
                else:
                    skipped_for_authorship_message = ""

                if isinstance(contributor, GitHubContributor):
                    body_contributions += f"\n#### @{contributor.github_username}{missing_author_message}{skipped_for_authorship_message}\n"
                elif isinstance(contributor, GitCommitContributor):
                    name = contributor.git_name
                    email = contributor.git_email
                    if email:
                        body_contributions += (
                            f"\n#### {email}{missing_author_message}{skipped_for_authorship_message}\n"
                        )
                    else:
                        body_contributions += f"\n#### {name}{missing_author_message}{skipped_for_authorship_message}\n"
                else:
                    raise Exception(
                        "Invalid contributor: Must be GitHubContributor or GitCommitContributor."
                    )

                contributions_by_category = (
                    self.contribution_manager.get_contribution_categories_for(
                        contributor
                    )
                )
                for category, contribution_list in contributions_by_category.items():
                    contribution_category_name: str = (
                        self._split_pascal_case(
                            category.removeprefix("GitHubPullRequest").removesuffix(
                                "Contributor"
                            )
                        )
                        .title()
                        .strip()
                    )
                    body_contributions += f"- **{contribution_category_name}**\n"
                    for contribution in contribution_list:
                        if isinstance(
                            contribution, GitHubPullRequestCommitContribution
                        ):
                            body_contributions += f"  - [`{contribution.id[:7]}`](https://github.com/{self.repo_for_compare}/commit/{contribution.id})\n"
                        else:
                            body_contributions += f"  - [Link]({contribution.id})\n"
            
            body_contributions += "\n"
            body_contributions += f'**Note:** Contributors marked "(Skip for recommended or required authorship)" were manually skipped for new authorship consideration. If they were already present in the `{cff_path}` file, or if a user manually adds them to the `{cff_path}` file as part of this pull request, their author entry will remain. The skip command only prevents the GitHub Action from recommending or requiring authorship.'            
            body_contributions += "\n"

        else:
            body_contributions += "\n**No contributions.**\n"

        body = f"""
{marker}
### CFF Author Updater ###

{body_pr_validation_status}

{body_contributions}
"""
        if self.missing_authors:
            body += f"""
**Recommended `{cff_path}` file (updated with missing authors):**
```yaml
{yaml.dump(cff, sort_keys=False)}
```
"""
            body += (
                f"***Important: This recommended `{cff_path}` file has not been changed yet on this pull request. "
                f"It can be manually copied and committed to the repository. For GitHub users to be recognized, "
                f"you must use their GitHub user profile URL as their `alias` in the {cff_path} file."
            )
            if self.missing_author_invalidates_pr:
                body += f" If the `{cff_path}` file is missing any contributor qualified for authorship from the pull request, the pull request will remain invalid. You may [manually skip or unskip specific contributors for authorship](https://github.com/willynilly/cff-author-updater/blob/v{self.github_action_version}/README.md#-manual-overrides-skip--unskip-contributors-for-authorship) by posting special pull request comments."
            body += "***"
        else:
            duplicate_author_error_message: str = (
                ", but has at least one duplicate author."
                if self.duplicate_authors
                else ""
            )
            body += f"**Current `{cff_path}` file (contains all qualified authors from this pull request{duplicate_author_error_message}).**"

            if self.duplicate_authors and self.duplicate_author_invalidates_pr:
                body += f"The pull request will remain invalid until no duplicate authors exist in the `{cff_path}` file."
            body += f"""
```yaml
{yaml.dump(original_cff, sort_keys=False)}
```
"""

        if error_logs:
            if Flags.has("show_error_messages_in_pr_comment"):
                body += "\n\n**🚨 Errors:**\n" + "\n".join(["- " + e for e in error_logs])
            else:
                body += "\n\n**🚨 Errors:**\n" + "The pull request has errors. Please check the logs for details."

        if warning_logs:
            if Flags.has("show_warning_messages_in_pr_comment"):
                body += "\n\n**⚠️ Warnings:**\n" + "\n".join(["- " + w for w in warning_logs])
            else:
                body += "\n\n**⚠️ Warnings:**\n" + "The pull request has warnings. Please check the logs for details."

        if info_logs:
            if Flags.has("show_info_messages_in_pr_comment"):
                body += "\n\n**ℹ️ Info:**\n" + "\n".join(["- " + i for i in info_logs])
            else:
                body += "\n\n**ℹ️ Info:**\n" + "The pull request has info messages. Please check the logs for details."
            
        body += f"""

_Last updated: {timestamp} UTC · Commit [`{commit_sha_short}`]({commit_url})_

***Powered by [CFF Author Updater v{self.github_action_version}](https://github.com/willynilly/cff-author-updater)***
"""
        return body
