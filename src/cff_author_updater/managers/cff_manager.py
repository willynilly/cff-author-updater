import copy
import json
from pathlib import Path
import requests
import yaml

from cff_author_updater.cff_file import CffFile
from cff_author_updater.contributors.cff_author_contributor import CffAuthorContributor
from cff_author_updater.contributors.contributor import Contributor
from cff_author_updater.contributors.git_commit_contributor import GitCommitContributor
from cff_author_updater.contributors.github_contributor import (
    GitHubContributor,
    parse_github_username_from_github_profile_url,
    is_github_user_profile_url,
)
from cff_author_updater.flags import Flags
from cff_author_updater.managers.github_manager import GithubManager
from cff_author_updater.managers.orcid_manager import OrcidManager


class CffManager:

    def __init__(
        self, cff_path: Path, github_manager: GithubManager, orcid_manager: OrcidManager
    ):
        self.github_manager = github_manager
        self.orcid_manager = orcid_manager
        self.cff_path = cff_path
        self.cff_file = CffFile(cff_path=cff_path)

    def get_contribution_note_for_warning(
        self,
        contributor: GitCommitContributor | GitHubContributor,
        contribution_details: dict,
        repo_for_compare: str,
    ) -> str:
        """
        Get contribution note for warning.
        Args:
            contributor (GitCommitContributor | GitHubContributor): The contributor.
            contribution_details (dict): Contribution details.
            repo_for_compare (str): Repository for comparison
        Returns:
            str: Contribution note.
        """
        contribution_categories = [
            ("commits", "Commit"),
            ("pr_comments", "Pull Request Comment"),
            ("reviews", "Review"),
            ("issues", "Issue"),
            ("issue_comments", "Issue Comment"),
        ]

        contribution_note: str = ""
        if isinstance(contributor, GitCommitContributor):
            contributor_name = contributor.git_name
            contributor_email = contributor.git_email
            if contributor_email and contributor_name:
                contribution_note = f"- `{contributor_name} <{contributor_email}>`: "
            elif contributor_name:
                contribution_note = f"- `{contributor_name}`: "
            elif contributor_email:
                contribution_note = f"- `{contributor_email}`: "
            else:
                raise ValueError(
                    "GitCommitContributor must contain at least an git name or git email."
                )
        elif isinstance(contributor, GitHubContributor):
            github_username = contributor.github_username
            if not github_username:
                raise ValueError("GitHubContributor must have a GitHub username.")
            contribution_note = f"- @{github_username}: "
        else:
            raise ValueError(
                "Contributor must be either a GitCommitContributor or a GitHubContributor."
            )

        # Find the first contribution category that exists in the contribution details
        # and is not empty

        first_contribution_category: tuple[str, str] | None = None
        for contribution_category in contribution_categories:
            if (
                contribution_category[0] in contribution_details.get(contributor, {})
                and len(contribution_details[contributor][contribution_category[0]]) > 0
            ):
                first_contribution_category = contribution_category
                break
        if first_contribution_category:
            first_contribution = contribution_details[contributor][
                first_contribution_category[0]
            ][0]
            if first_contribution_category[0] == "commits":
                sha = first_contribution
                sha_url = f"https://github.com/{repo_for_compare}/commit/{sha}"
                contribution_note += f"Commit: [`{first_contribution[:7]}`]({sha_url})"
            else:
                contribution_note += (
                    f"[{first_contribution_category[1]}]({first_contribution})"
                )
        else:
            raise Exception("No contribution found for the contributor.")
        return contribution_note

    def create_cff_author_contributor_from_github_contributor(
        self,
        github_contributor: GitHubContributor,
        token: str,
        warnings: list[str],
        logs: list[str],
        contribution_note: str,
    ) -> CffAuthorContributor | None:
        contributor = github_contributor
        a: dict = {}

        # Github user contributor
        user_url: str = f"https://api.github.com/users/{contributor.github_username}"
        resp: requests.Response = requests.get(
            user_url, headers={"Authorization": f"token {token}"}
        )

        # skip the user if the user is not found
        if resp.status_code != 200:
            warnings.append(
                f"- @{contributor.github_username}: Unable to fetch user data from GitHub API. Status code: {resp.status_code}{contribution_note}"
            )
            return None

        # determine the type of user
        user = resp.json()
        user_type = user.get("type")
        user_profile_url: str = f"https://github.com/{contributor.github_username}"

        if user_type == "Organization":
            a["name"] = user.get("name") or contributor.github_username
            a["alias"] = user_profile_url
            if user.get("email"):
                a["email"] = user["email"]
        else:
            full_name: str = user.get("name") or contributor.github_username
            name_parts: list[str] = full_name.split(" ", 1)

            if len(name_parts) > 1:
                a["given-names"] = name_parts[0]
                a["family-names"] = name_parts[1]
                a["alias"] = user_profile_url
            else:
                a["name"] = full_name
                a["alias"] = user_profile_url
                warnings.append(
                    f"- @{contributor.github_username}: Only one name part found, treated as entity for deduplication consistency.{contribution_note}"
                )
                return CffAuthorContributor(cff_author_data=a)

            if user.get("email"):
                a["email"] = user["email"]
            orcid = self.orcid_manager.extract_orcid(text=user.get("bio"))
            if not orcid and full_name:
                orcid = self.orcid_manager.search_orcid(
                    full_name=full_name, email=user.get("email"), logs=logs
                )
            if orcid and self.orcid_manager.validate_orcid(orcid=orcid):
                a["orcid"] = f"https://orcid.org/{orcid}"
            elif orcid:
                warnings.append(
                    f"- @{contributor.github_username}: ORCID `{orcid}` is invalid or unreachable."
                )
            else:
                warnings.append(f"- @{contributor.github_username}: No ORCID found.")

        return CffAuthorContributor(cff_author_data=a)

    def create_cff_author_contributor_from_git_commit_contributor(
        self,
        git_commit_contributor: GitCommitContributor,
        cff: dict,
        warnings: list[str],
        logs: list[str],
        contribution_note: str,
    ) -> CffAuthorContributor | None:
        contributor = git_commit_contributor
        name = contributor.git_name
        email = contributor.git_email
        name_parts: list[str] = name.split(" ", 1)
        new_cff_author_dict: dict = {}

        if len(name_parts) > 1:
            new_cff_author_dict["given-names"] = name_parts[0]
            new_cff_author_dict["family-names"] = name_parts[1]
            if email:
                new_cff_author_dict["email"] = email
            orcid = self.orcid_manager.search_orcid(name, email, logs)
            if orcid and self.orcid_manager.validate_orcid(orcid):
                new_cff_author_dict["orcid"] = f"https://orcid.org/{orcid}"
            elif orcid:
                warnings.append(
                    f"- `{name}`: ORCID `{orcid}` is invalid or unreachable."
                )
            else:
                warnings.append(f"- `{name}`: No ORCID found.")
        else:
            new_cff_author_dict["name"] = name
            if email:
                new_cff_author_dict["email"] = email
            warnings.append(
                f"- `{name}`: Only one name part found, treated as entity for deduplication consistency.{contribution_note}"
            )
        return CffAuthorContributor(cff_author_data=new_cff_author_dict)

    def create_identifier_of_cff_author_for_warning(
        self, cff_author: CffAuthorContributor
    ):
        a = cff_author.cff_author_data
        if cff_author is None:
            raise ValueError(
                f"Cannot create identifier for CFF Author: cff_author cannot be None."
            )
        if "alias" in a:
            username: str | None = parse_github_username_from_github_profile_url(
                url=a["alias"]
            )
            if username is None:
                raise ValueError(
                    f"Cannot create identifier for CFF Author: cff_author has an invalid github profile url {a['alias']}."
                )
            else:
                return "@" + username
        elif "email" in a:
            return a["email"]
        elif "name" in a:
            return a["name"]
        else:
            raise ValueError(
                f"Cannot create identifier for CFF author: cff_author must have an alias, email, or name."
            )

    def validate_old_cff_authors_are_unique(
        self, cff: dict, warnings: list[str]
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
            author_a_identifier = self.create_identifier_of_cff_author_for_warning(
                cff_author=author_a
            )
            for j in range(i + 1, len(old_authors)):
                author_b = old_authors[j]
                if author_a.is_same_author(cff_author=author_b):
                    author_b_identifier = (
                        self.create_identifier_of_cff_author_for_warning(
                            cff_author=author_b
                        )
                    )
                    duplicate_authors.add(author_b)
                    duplication_message: str = (
                        f"The original CFF file has these duplicate authors: {author_a_identifier} and {author_b_identifier}"
                    )
                    warnings.append(duplication_message)
        return duplicate_authors

    def update_cff(
        self,
        contributors: set[GitCommitContributor | GitHubContributor],
        token: str,
        repo: str,
        pr_number: str,
        output_file: str,
        repo_for_compare: str,
        contribution_details: dict,
    ) -> tuple[
        set[GitCommitContributor | GitHubContributor], set[CffAuthorContributor]
    ]:
        """
        Process contributors and update the CFF file.
        Args:
            contributors (set): Set of contributors.
            token (str): GitHub token.
            repo (str): Repository name.
            pr_number (str): Pull request number.
            output_file (str): Output file path.
            repo_for_compare (str): Repository for comparison.
            contribution_details (dict): Contribution details.
        """
        if not isinstance(contributors, set):
            raise ValueError("Contributors must be a set.")

        if not token:
            raise ValueError("GitHub token is not provided.")

        if not repo:
            raise ValueError("Repository is not provided.")

        if not pr_number:
            raise ValueError("Pull request number is not provided.")

        if not output_file:
            raise ValueError("Output file path is not provided.")

        cff = copy.deepcopy(self.cff_file.cff)

        cff.setdefault("authors", [])

        warnings: list = []
        logs: list = []

        # validate old authors
        duplicate_authors: set = self.validate_old_cff_authors_are_unique(
            cff=cff, warnings=warnings
        )

        # update new authors
        already_in_cff_contributors: set[GitCommitContributor | GitHubContributor] = (
            set()
        )

        for contributor in contributors:
            new_cff_author: CffAuthorContributor | None = None

            contribution_note = self.get_contribution_note_for_warning(
                contributor=contributor,
                contribution_details=contribution_details,
                repo_for_compare=repo_for_compare,
            )

            if isinstance(contributor, GitHubContributor):
                new_cff_author = (
                    self.create_cff_author_contributor_from_github_contributor(
                        github_contributor=contributor,
                        token=token,
                        contribution_note=contribution_note,
                        warnings=warnings,
                        logs=logs,
                    )
                )
            elif isinstance(contributor, GitCommitContributor):
                new_cff_author = (
                    self.create_cff_author_contributor_from_git_commit_contributor(
                        git_commit_contributor=contributor,
                        cff=cff,
                        contribution_note=contribution_note,
                        warnings=warnings,
                        logs=logs,
                    )
                )
            else:
                raise Exception("Invalid contributor class.")

            if new_cff_author is None:
                continue
            else:
                if any(
                    new_cff_author.is_same_author(
                        cff_author=CffAuthorContributor(
                            cff_author_data=existing_cff_author
                        )
                    )
                    for existing_cff_author in cff["authors"]
                ):
                    identifier: str = self.create_identifier_of_cff_author_for_warning(
                        cff_author=new_cff_author
                    )
                    already_in_cff_contributors.add(contributor)
                    warnings.append(
                        f"- {identifier}: Already exists in CFF file or already added from another new contribution."
                    )
                    continue

            cff["authors"].append(new_cff_author.cff_author_data)

        self.cff_file.cff = cff
        self.cff_file.save()

        with open(output_file, "a") as f:
            f.write("new_authors<<EOF\n")
            f.write(
                self.create_json_for_contribution_details(
                    contribution_details=contribution_details
                )
            )
            f.write("\nEOF\n")
            f.write("updated_cff<<EOF\n")
            f.write(yaml.dump(cff, sort_keys=False))
            f.write("\nEOF\n")
            if warnings:
                f.write("warnings<<EOF\n" + "\n".join(warnings) + "\nEOF\n")
            if logs:
                f.write("orcid_logs<<EOF\n" + "\n".join(logs) + "\nEOF\n")

        missing_authors: set = contributors - already_in_cff_contributors
        if Flags.has("post_pr_comment") and pr_number:
            self.github_manager.post_pull_request_comment(
                cff_file=self.cff_file,
                warnings=warnings,
                logs=logs,
                token=token,
                repo=repo,
                pr_number=pr_number,
                contribution_details=contribution_details,
                repo_for_compare=repo_for_compare,
                missing_authors=missing_authors,
                missing_author_invalidates_pr=Flags.has(
                    "missing_author_invalidates_pr"
                ),
                duplicate_authors=duplicate_authors,
                duplicate_author_invalidates_pr=Flags.has(
                    "duplicate_author_invalidates_pr"
                ),
            )

        return missing_authors, duplicate_authors

    def create_json_for_contribution_details(self, contribution_details: dict) -> str:
        normalized = []
        for contributor, contributions in contribution_details.items():
            normalized_contributor = {
                "contributor": contributor.to_dict(),
                "contributions": contributions,
            }
            normalized.append(normalized_contributor)
        return json.dumps(normalized)
