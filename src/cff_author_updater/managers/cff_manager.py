import copy
import json
import logging
from pathlib import Path

import yaml

from cff_author_updater.cff_author_review import CffAuthorReview
from cff_author_updater.cff_file import CffFile, CffFileValidationError
from cff_author_updater.contributions.github_pull_request_commit_contribution import (
    GitHubPullRequestCommitContribution,
)
from cff_author_updater.contributors.cff_author_contributor import CffAuthorContributor
from cff_author_updater.contributors.contributor import Contributor
from cff_author_updater.contributors.git_commit_contributor import GitCommitContributor
from cff_author_updater.contributors.github_contributor import (
    GitHubContributor,
)
from cff_author_updater.flags import Flags
from cff_author_updater.log_identifiers import (
    create_identifier_of_cff_author_for_logger,
    create_identifier_of_contributor_for_logger,
)
from cff_author_updater.logging_config import get_log_collector
from cff_author_updater.managers.contribution_manager import ContributionManager
from cff_author_updater.managers.github_pull_request_manager import (
    GitHubPullRequestManager,
)

logger = logging.getLogger(__name__)


class CffManager:

    CONTRIBUTION_CATEGORIES = [
        ("GitHubPullRequestCommitContribution", "Commit"),
        ("GitHubPullRequestCommentContribution", "Pull Request Comment"),
        ("GitHubPullRequestReviewContribution", "Review"),
        ("GitHubPullRequestIssueContribution", "Issue"),
        ("GitHubPullRequestIssueCommentContribution", "Issue Comment"),
    ]

    def __init__(
        self,
        cff_path: Path,
        github_pull_request_manager: GitHubPullRequestManager,
    ):
        self.github_pull_request_manager = github_pull_request_manager
        self.orcid_manager = github_pull_request_manager.orcid_manager
        self.cff_path = cff_path

    def _get_contribution_warning_postfix(
        self,
        contributor: GitCommitContributor | GitHubContributor,
        contribution_manager: ContributionManager,
    ) -> str:
        """
        Get contribution warning prefix.
        Args:
            contributor (GitCommitContributor | GitHubContributor): The contributor.
            contribution_manager (ContributionManager): Contribution manager.
        Returns:
            str: Contribution warning prefix.
        """
        repo_for_compare = self.github_pull_request_manager.repo_for_compare

        contribution_warning_postfix: str = ""
        if isinstance(contributor, GitCommitContributor):
            contributor_name = contributor.git_name
            contributor_email = contributor.git_email
            if contributor_email and contributor_name:
                contribution_warning_postfix = (
                    f"- `{contributor_name} <{contributor_email}>`: "
                )
            elif contributor_name:
                contribution_warning_postfix = f"- `{contributor_name}`: "
            elif contributor_email:
                contribution_warning_postfix = f"- `{contributor_email}`: "
            else:
                raise ValueError(
                    "GitCommitContributor must contain at least an git name or git email."
                )
        elif isinstance(contributor, GitHubContributor):
            github_username = contributor.github_username
            if not github_username:
                raise ValueError("GitHubContributor must have a GitHub username.")
            contribution_warning_postfix = f"- @{github_username}: "
        else:
            raise ValueError(
                "Contributor must be either a GitCommitContributor or a GitHubContributor."
            )

        # Find the first contribution category that exists for the contributor in the contribution_mananager
        contributions_by_category = (
            contribution_manager.get_contribution_categories_for(
                contributor=contributor
            )
        )

        first_contribution_category: tuple[str, str] | None = None
        for contribution_category in self.CONTRIBUTION_CATEGORIES:
            if (
                contribution_category[0] in contributions_by_category
                and len(contributions_by_category[contribution_category[0]]) > 0
            ):
                first_contribution_category = contribution_category
                break
        if first_contribution_category:
            first_contribution = contributions_by_category[
                first_contribution_category[0]
            ][0]
            if isinstance(first_contribution, GitHubPullRequestCommitContribution):
                sha = first_contribution.sha
                sha_url = f"https://github.com/{repo_for_compare}/commit/{sha}"
                contribution_warning_postfix += f"Commit: [`{sha[:7]}`]({sha_url})"
            else:
                contribution_warning_postfix += (
                    f"[{first_contribution_category[1]}]({first_contribution})"
                )
        else:
            raise ValueError(
                f"No contribution found for the contributor: {contributor.to_dict()}. "
                f"Categories checked: {[c[0] for c in self.CONTRIBUTION_CATEGORIES]}. "
                f"Categories present: {list(contributions_by_category.keys())}."
            )

        return contribution_warning_postfix

    def create_cff_author_contributor_from_github_contributor(
        self,
        github_contributor: GitHubContributor,
        contribution_warning_postfix: str,
    ) -> CffAuthorContributor | None:
        contributor = github_contributor
        github_username: str | None = contributor.github_username
        github_user_profile_url: str | None = contributor.github_user_profile_url
        is_valid_github_user: bool = contributor.is_valid_github_user
        name: str | None = contributor.name
        email: str | None = contributor.email
        orcid: str | None = contributor.orcid
        is_organization: bool = contributor.is_organization

        new_cff_author_data: dict = {}

        # skip the github contributor if it has an invalid github user name
        if not is_valid_github_user:
            logger.warning(
                f"Cannot create CFF author for @{github_username}: invalid GitHub username."
            )
            return None

        full_name: str = name or github_username

        if is_organization:
            new_cff_author_data["name"] = full_name
        else:
            name_parts: list[str] = full_name.split(" ", 1)

            if len(name_parts) > 1:
                new_cff_author_data["given-names"] = name_parts[0]
                new_cff_author_data["family-names"] = name_parts[1]
            else:
                new_cff_author_data["name"] = full_name
                logger.info(
                    f"@{github_username}: Only one name part found, treated as entity for deduplication consistency.{contribution_warning_postfix}"
                )

        new_cff_author_data["alias"] = github_user_profile_url

        if email:
            new_cff_author_data["email"] = email

        if orcid:
            new_cff_author_data["orcid"] = orcid
        
        return CffAuthorContributor(cff_author_data=new_cff_author_data)

    def create_cff_author_contributor_from_git_commit_contributor(
        self,
        git_commit_contributor: GitCommitContributor,
        contribution_warning_postfix: str,
    ) -> CffAuthorContributor | None:
        contributor = git_commit_contributor
        name = contributor.git_name
        email = contributor.git_email
        orcid = contributor.orcid
        name_parts: list[str] = name.split(" ", 1)
        new_cff_author_data: dict = {}

        if len(name_parts) > 1:
            new_cff_author_data["given-names"] = name_parts[0]
            new_cff_author_data["family-names"] = name_parts[1]
        else:
            new_cff_author_data["name"] = name
            logger.info(
                f"`{name}`: Only one name part found, treated as entity for deduplication consistency.{contribution_warning_postfix}"
            )
        if email:
            new_cff_author_data["email"] = email
        if orcid:
            new_cff_author_data["orcid"] = orcid
        return CffAuthorContributor(cff_author_data=new_cff_author_data)

    
    def validate_old_cff_authors_are_unique(
        self, cff: dict
    ) -> set[CffAuthorContributor]:
        # create warning messages if old authors are not unique

        # assume that old authors listed earlier in the CFF file
        # are "older" than those listed later in the CFF file
        duplicate_authors: set[CffAuthorContributor] = set()
        old_authors: list[CffAuthorContributor] = [
            CffAuthorContributor(cff_author_data=cff_author_data)
            for cff_author_data in cff["authors"]
        ]
        for i, author_a in enumerate(old_authors):
            author_a_identifier = create_identifier_of_cff_author_for_logger(
                cff_author=author_a
            )
            for j in range(i + 1, len(old_authors)):
                author_b = old_authors[j]
                if author_a.is_same_author(cff_author=author_b):
                    author_b_identifier = (
                        create_identifier_of_cff_author_for_logger(
                            cff_author=author_b
                        )
                    )
                    duplicate_authors.add(author_b)
                    duplication_message: str = (
                        f"The original CFF file has these duplicate authors: {author_a_identifier} and {author_b_identifier}"
                    )
                    if Flags.has("duplicate_author_invalidates_pr"):
                        logger.error(duplication_message)
                    else:
                        logger.warning(duplication_message)

        return duplicate_authors

    def _process_cff_validation_errors(
        self, cff_file_validation_error: CffFileValidationError
    ) -> None:
        """
        Process CFF validation errors and log them.
        Args:
            cff_file_validation_error (CffFileValidationError): CFF file validation error.
        """
        for error in cff_file_validation_error.cffconvert_validation_duplicate_errors:
            if Flags.has("duplicate_author_invalidates_pr") or Flags.has(
                "invalid_cff_invalidates_pr"
            ):
                logger.error(
                    f"[cffconvert] Invalid CFF because duplicate author: {error}"
                )
            else:
                logger.warning(
                    f"[cffconvert] Invalid CFF because duplicate author: {error}"
                )

        for error in cff_file_validation_error.cffconvert_validation_other_errors:
            if Flags.has("invalid_cff_invalidates_pr"):
                logger.error(f"[cffconvert] Invalid CFF: {error}")
            else:
                logger.warning(f"[cffconvert] Invalid CFF: {error}")

    def update_cff(
        self,
        contribution_manager: ContributionManager,
    ) -> tuple[
        set[Contributor],
        set[CffAuthorContributor],
        list[str],
    ]:
        """
        Process contributors and update the CFF file.
        Args:
            contribution_manager (ContributionManager): Contribution manager.
        """
        if not isinstance(contribution_manager, ContributionManager):
            raise ValueError("Contribution manager is not provided.")

        repo = self.github_pull_request_manager.repo
        pr_number = self.github_pull_request_manager.pr_number
        output_file = self.github_pull_request_manager.output_file

        if not repo:
            raise ValueError("Repository is not provided.")

        if not pr_number:
            raise ValueError("Pull request number is not provided.")

        if not output_file:
            raise ValueError("Output file path is not provided.")

        skip_commands: dict[str, set[str]] = {}
        if Flags.has("can_skip_authorship"):
           skip_commands = self.github_pull_request_manager.scan_pr_comments_for_skip_commands()

        cffconvert_validation_errors: list[str] = []

        original_cff_is_valid_cff: bool = False
        try:
            self.cff_file = CffFile(cff_path=self.cff_path, validate=True)
            original_cff_is_valid_cff = True
        except CffFileValidationError as e:
            self.cff_file = CffFile(cff_path=self.cff_path, validate=False)
            self._process_cff_validation_errors(cff_file_validation_error=e)
            cffconvert_validation_errors += e.cffconvert_validation_errors

        cff = copy.deepcopy(self.cff_file.cff)

        cff.setdefault("authors", [])

        # validate old authors
        duplicate_authors: set[CffAuthorContributor] = self.validate_old_cff_authors_are_unique(cff=cff)

        # update new authors
        already_in_cff_contributors: set[GitCommitContributor | GitHubContributor] = (
            set()
        )

        contributors: set[Contributor] = set(contribution_manager.contributors)

        logger.debug(f'before contributors {[c.to_dict() for c in contributors]}')

        for contributor in contributors:

            logger.debug(f'contributor {contributor.to_dict()} {contributor.__class__.__name__}')


            if self.github_pull_request_manager.should_skip_contributor(contributor, skip_commands):
                identifier = create_identifier_of_contributor_for_logger(contributor)
                logger.info(f"Skipping contributor based on skip command: {identifier}")
                continue

            new_cff_author: CffAuthorContributor | None = None

            if isinstance(contributor, GitHubContributor) or isinstance(
                contributor, GitCommitContributor
            ):
                contribution_warning_postfix = self._get_contribution_warning_postfix(
                    contributor=contributor,
                    contribution_manager=contribution_manager,
                )
            else:
                raise ValueError(
                    "Contributor must be either a GitCommitContributor or a GitHubContributor."
                )

            if isinstance(contributor, GitHubContributor):

                new_cff_author = (
                    self.create_cff_author_contributor_from_github_contributor(
                        github_contributor=contributor,
                        contribution_warning_postfix=contribution_warning_postfix,
                    )
                )
            elif isinstance(contributor, GitCommitContributor):
                new_cff_author = (
                    self.create_cff_author_contributor_from_git_commit_contributor(
                        git_commit_contributor=contributor,
                        contribution_warning_postfix=contribution_warning_postfix,
                    )
                )
            else:
                raise Exception("Invalid contributor class.")

            if new_cff_author is None:
                logger.debug('new_cff_author is None, skipping contributor')
                continue
            else:

                logger.debug(f'new_cff_author {new_cff_author.to_dict(), new_cff_author.__class__.__name__}')

                # this checks the contributor for skipping after it has been enriched with orcid information 
                if self.github_pull_request_manager.should_skip_contributor(contributor=new_cff_author, skip_commands=skip_commands):
                    identifier = create_identifier_of_cff_author_for_logger(cff_author=new_cff_author)
                    logger.info(f"Skipping contributor based on skip command: {identifier}")
                    continue

                if any(
                    new_cff_author.is_same_author(
                        cff_author=CffAuthorContributor(
                            cff_author_data=existing_cff_author
                        )
                    )
                    for existing_cff_author in cff["authors"]
                ):
                    identifier: str = create_identifier_of_cff_author_for_logger(
                        cff_author=new_cff_author
                    )
                    already_in_cff_contributors.add(contributor)
                    # Correct behavior: this is OK — the author is now in CFF
                    logger.info(f"{identifier}: Already exists in CFF file — OK.")
                    continue
                    

            cff["authors"].append(new_cff_author.cff_author_data)

        self.cff_file.cff = cff
        updated_cff_is_valid_cff: bool = original_cff_is_valid_cff
        if original_cff_is_valid_cff:
            try:
                self.cff_file.save()
            except CffFileValidationError as e:
                updated_cff_is_valid_cff = False
                self._process_cff_validation_errors(cff_file_validation_error=e)
                cffconvert_validation_errors += e.cffconvert_validation_errors

        
        missing_authors: set[Contributor] = contributors - already_in_cff_contributors

        self._add_additional_logs(contribution_manager=contribution_manager, missing_authors=missing_authors, duplicate_authors=duplicate_authors, cffconvert_validation_errors=cffconvert_validation_errors)

        logger.debug(f'after contributors {[c.to_dict() for c in contributors]}')
        logger.debug(f'already_in_cff_contributors {[c.to_dict() for c in already_in_cff_contributors]}')
        logger.debug(f'missing_authors {[c.to_dict() for c in missing_authors]}')

        if Flags.has("post_pr_comment") and pr_number:
            
            cff_author_review: CffAuthorReview = CffAuthorReview(
                cff_file=self.cff_file,
                github_pull_request_manager=self.github_pull_request_manager,
                contribution_manager=contribution_manager,
                missing_authors=missing_authors,
                missing_author_invalidates_pr=Flags.has(
                    "missing_author_invalidates_pr"
                ),
                duplicate_authors=duplicate_authors,
                duplicate_author_invalidates_pr=Flags.has(
                    "duplicate_author_invalidates_pr"
                ),
                cffconvert_validation_errors=cffconvert_validation_errors
            )

            self.github_pull_request_manager.post_pull_request_comment(
                comment_body=cff_author_review.get_review(),
            )
        
        # collect and output final logs
        log_collector = get_log_collector()
        error_logs = log_collector.get_error_logs(is_unique=False)
        warning_logs = log_collector.get_warning_logs(is_unique=False)
        info_logs = log_collector.get_info_logs(is_unique=False)

        # Determine the log level and collect debug logs if applicable
        log_level = logging.getLevelName(logger.getEffectiveLevel())
        if log_level == 'DEBUG':
            debug_logs = log_collector.get_debug_logs(is_unique=False)
        else:
            debug_logs = []

        with open(output_file, "a") as f:
            f.write(
                f"original_cff_is_valid_cff={'true' if original_cff_is_valid_cff else 'false'}\n"
            )
            f.write(
                f"updated_cff_is_valid_cff={'true' if updated_cff_is_valid_cff else 'false'}\n"
            )
            f.write(
                f"updated_cff_has_error={'true' if len(error_logs) > 0 else 'false'}\n"
            )
            f.write(
                f"updated_cff_has_warning={'true' if len(warning_logs) > 0 else 'false'}\n"
            )
            f.write("new_authors<<EOF\n")
            f.write(
                self.create_json_for_contribution_manager(
                    contribution_manager=contribution_manager
                )
            )
            f.write("\nEOF\n")

            f.write("original_cff<<EOF\n")
            f.write(yaml.dump(self.cff_file.original_cff, sort_keys=False))
            f.write("\nEOF\n")

            f.write("updated_cff<<EOF\n")
            f.write(yaml.dump(cff, sort_keys=False))
            f.write("\nEOF\n")

            if error_logs:
                f.write("error_log<<EOF\n" + "\n".join(error_logs) + "\nEOF\n")
            if warning_logs:
                f.write("warning_log<<EOF\n" + "\n".join(warning_logs) + "\nEOF\n")
            if info_logs:
                f.write("info_log<<EOF\n" + "\n".join(info_logs) + "\nEOF\n")
            if debug_logs:
                f.write("debug_log<<EOF\n" + "\n".join(debug_logs) + "\nEOF\n")


        return missing_authors, duplicate_authors, cffconvert_validation_errors

    

    def _add_additional_logs(self, contribution_manager: ContributionManager, missing_authors: set[Contributor], duplicate_authors: set[CffAuthorContributor], cffconvert_validation_errors: list[str]) -> None:
        new_authors_count = len(contribution_manager.contributors)
        if new_authors_count > 0:
            logger.info(
                f"The recommended `{self.cff_file.cff_path}` file has been updated with {new_authors_count} new authors."
            )
            

            if Flags.has("missing_author_invalidates_pr") and len(missing_authors):
                logger.error(
                    f"Pull request is invalidated because {len(missing_authors)} new author(s) are missing from the `{self.cff_file.cff_path}` file."
                )

                for contributor in missing_authors:
                    identifier = create_identifier_of_contributor_for_logger(contributor)
                    
                    reason = ""
                    
                    if isinstance(contributor, GitHubContributor):
                        reason = (
                            f"unmatched CFF author — possible cause: existing `{self.cff_file.cff_path}` entry is missing an 'alias' with this GitHub profile URL: "
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
                
        if Flags.has("duplicate_author_invalidates_pr") and len(duplicate_authors):
            logger.error(
                f"Pull request is invalidated because there is a duplicate author in the `{self.cff_file.cff_path}` file."
            )
        if Flags.has("invalid_cff_invalidates_pr") and len(cffconvert_validation_errors):
            logger.error(
                f"Pull request is invalidated because the `{self.cff_file.cff_path}` file is not valid CFF.\n"
                + "\n".join(cffconvert_validation_errors)
            )

    def create_json_for_contribution_manager(
        self, contribution_manager: ContributionManager
    ) -> str:
        normalized = []
        for (
            contributor
        ) in contribution_manager.contributors_sorted_by_first_contribution:
            contributions: list[dict] = [
                contribution.to_dict()
                for contribution in contribution_manager.get_contributions_for(
                    contributor=contributor
                )
            ]
            normalized_contributor = {
                "contributor": contributor.to_dict(),
                "contributions": contributions,
            }
            normalized.append(normalized_contributor)
        return json.dumps(normalized)
