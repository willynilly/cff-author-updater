import copy
import json
from pathlib import Path
import requests
import yaml

from cff_author_updater.cff_file import CffFile
from cff_author_updater.contributors.git_commit_contributor import GitCommitContributor
from cff_author_updater.contributors.github_user_contributor import (
    GitHubUserContributor,
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

    def is_same_cff_author(self, cff_author_a: dict, cff_author_b: dict):
        a = cff_author_a
        b = cff_author_b

        a_type: str = self.get_cff_author_type(a)
        b_type: str = self.get_cff_author_type(b)

        if a_type == "unknown" or b_type == "unknown":
            raise ValueError("Cannot compare unknown author types.")

        # Match in the following order (case-insensitive and surrounding whitespace insensitive):
        # 1. orcid
        # 2. email
        # 3. alias (only using GitHub user profile URL)
        # 4. full name (using given-names + ' ' + family-names if type person, or 'name' that has at least two parts if type is entity)
        # when comparing full names, the authors are the same only if one of the following applies:
        # the authors are of the same CFF type (both persons or both entities)
        # the authors

        # match orcid
        a_orcid = a.get("orcid", "").casefold().strip()
        b_orcid = b.get("orcid", "").casefold().strip()
        if a_orcid and a_orcid == b_orcid:
            return True

        # else, match on email
        a_email = a.get("email", "").casefold().strip()
        b_email = b.get("email", "").casefold().strip()
        if a_email and a_email == b_email:
            return True

        # else match on alias if and only if it's a GitHub user profile URL
        a_alias = a.get("alias", "").casefold().strip()
        b_alias = b.get("alias", "").casefold().strip()
        a_is_github_user = is_github_user_profile_url(url=a_alias)
        b_is_github_user = is_github_user_profile_url(url=b_alias)
        if a_alias and b_alias == b_alias and a_is_github_user:
            return True

        # else match on full name
        # for persons, full name is 'given-names' + ' ' + 'family-names'
        # for entities, full name is 'name'

        if a_type == "person":
            a_fullname: str = (
                f"{a.get('given-names', '').casefold().strip()} {a.get('family-names', '').casefold().strip()}".strip()
            )
        else:
            a_fullname: str = a.get("name", "").casefold().strip()

        if b_type == "person":
            b_fullname: str = (
                f"{b.get('given-names', '').casefold().strip()} {b.get('family-names', '').casefold().strip()}".strip()
            )
        else:
            b_fullname: str = b.get("name", "").casefold().strip()

        if not a_fullname or not b_fullname:
            raise ValueError(
                "Cannot compare an author that lacks an Orcid, email, alias, and name."
            )

        if a_fullname == b_fullname:
            # if they are both people with the same full name
            # of if they are both entities with same full name then
            # they are the same author, unless one of the following applies:
            # a) they have conflicting (and not just missing) orcid values
            # b) they have conflicting (and not just missing) github user profile URLs
            # in the alias (have a different alias that is not a github user profile URL
            # is permissible and not not qualify for this exception)
            # Note: authors with different emails
            # (like one that used a different email in their git commits than in the
            # CITATION.cff file) can be the same author as long as they have
            # the same full name, and do not have the aforementioned disqualifers
            # (i.e., conflicting Orcids or Github user profile URLs)

            a_has_orcid = a_orcid != ""
            b_has_orcid = b_orcid != ""
            a_github_user_profile_url = a_alias
            b_github_user_profile_url = b_alias
            if (a_has_orcid and b_has_orcid and a_orcid != b_orcid) or (
                a_is_github_user
                and b_is_github_user
                and a_github_user_profile_url != b_github_user_profile_url
            ):
                return False
            else:
                return True
        else:
            return False

    def get_cff_author_type(self, author: dict):
        if "name" in author:
            return "entity"
        elif "given-names" in author and "family-names" in author:
            return "person"
        else:
            return "unknown"

    def get_contribution_note_for_warning(
        self,
        contributor: str | tuple[str, str],
        contribution_details: dict,
        repo_for_compare: str,
    ) -> str:
        """
        Get contribution note for warning.
        Args:
            contributor (str): Contributor name.
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
                    "Contributor tuple must contain at least one non-empty string."
                )
        else:
            contributor_name = contributor
            if not contributor_name:
                raise ValueError("Contributor name must be a non-empty string.")
            contribution_note = f"- @{contributor_name}: "

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

    def create_cff_author_from_github_user_contributor(
        self,
        github_user_contributor: GitHubUserContributor,
        token: str,
        warnings: list[str],
        logs: list[str],
        contribution_note: str,
    ) -> dict | None:
        contributor = github_user_contributor
        entry: dict = {}

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
            entry["name"] = user.get("name") or contributor.github_username
            entry["alias"] = user_profile_url
            if user.get("email"):
                entry["email"] = user["email"]
        else:
            full_name: str = user.get("name") or contributor.github_username
            name_parts: list[str] = full_name.split(" ", 1)

            if len(name_parts) > 1:
                entry["given-names"] = name_parts[0]
                entry["family-names"] = name_parts[1]
                entry["alias"] = user_profile_url
            else:
                entry["name"] = full_name
                entry["alias"] = user_profile_url
                warnings.append(
                    f"- @{contributor.github_username}: Only one name part found, treated as entity for deduplication consistency.{contribution_note}"
                )
                return entry

            if user.get("email"):
                entry["email"] = user["email"]
            orcid = self.orcid_manager.extract_orcid(text=user.get("bio"))
            if not orcid and full_name:
                orcid = self.orcid_manager.search_orcid(
                    full_name=full_name, email=user.get("email"), logs=logs
                )
            if orcid and self.orcid_manager.validate_orcid(orcid=orcid):
                entry["orcid"] = f"https://orcid.org/{orcid}"
            elif orcid:
                warnings.append(
                    f"- @{contributor.github_username}: ORCID `{orcid}` is invalid or unreachable."
                )
            else:
                warnings.append(f"- @{contributor.github_username}: No ORCID found.")

        return entry

    def create_cff_author_from_git_commit_contributor(
        self,
        git_commit_contributor: GitCommitContributor,
        cff: dict,
        warnings: list[str],
        logs: list[str],
        contribution_note: str,
    ) -> dict | None:
        contributor = git_commit_contributor
        name = contributor.git_name
        email = contributor.git_email
        name_parts: list[str] = name.split(" ", 1)
        new_cff_author: dict = {}

        # check whether the git commit contributor
        # is already in the CFF file
        # based on comparing the git name
        # with the combination of given_names and family names
        # from the CFF file.
        # is so, use the CFF author information from the CFF file
        # instead of the Git Commit contributor
        for existing_cff_author in cff["authors"]:
            if (
                "given-names" in existing_cff_author
                and "family-names" in existing_cff_author
                and "email" in existing_cff_author
            ):
                existing_name = f"{existing_cff_author['given-names']} {existing_cff_author['family-names']}".strip().casefold()
                if (
                    existing_name == name.strip().casefold()
                    and existing_cff_author["email"].strip().casefold()
                    == email.strip().casefold()
                ):
                    # todo: should we add an option to enrich the existing author with their orcid?
                    return existing_cff_author

        if len(name_parts) > 1:
            new_cff_author["given-names"] = name_parts[0]
            new_cff_author["family-names"] = name_parts[1]
            if email:
                new_cff_author["email"] = email
            orcid = self.orcid_manager.search_orcid(name, email, logs)
            if orcid and self.orcid_manager.validate_orcid(orcid):
                new_cff_author["orcid"] = f"https://orcid.org/{orcid}"
            elif orcid:
                warnings.append(
                    f"- `{name}`: ORCID `{orcid}` is invalid or unreachable."
                )
            else:
                warnings.append(f"- `{name}`: No ORCID found.")
        else:
            new_cff_author["name"] = name
            if email:
                new_cff_author["email"] = email
            warnings.append(
                f"- `{name}`: Only one name part found, treated as entity for deduplication consistency.{contribution_note}"
            )
        return new_cff_author

    def create_identifier_of_cff_author_for_warning(self, cff_author: dict):
        if cff_author is None:
            raise ValueError(
                f"Cannot create identifier for CFF Author: cff_author cannot be None."
            )
        if "alias" in cff_author:
            username: str | None = parse_github_username_from_github_profile_url(
                url=cff_author["alias"]
            )
            if username is None:
                raise ValueError(
                    f"Cannot create identifier for CFF Author: cff_author has an invalid github profile url {cff_author['alias']}."
                )
            else:
                return "@" + username
        elif "email" in cff_author:
            return cff_author["email"]
        elif "name" in cff_author:
            return cff_author["name"]
        else:
            raise ValueError(
                f"Cannot create identifier for CFF author: cff_author must have an alias, email, or name."
            )

    def validate_old_cff_authors_are_unique(
        self, cff: dict, warnings: list[str], duplicate_author_invalidates_pr: bool
    ):
        # create warning messages if old authors are not unique

        # assume that old authors listed earlier in the CFF file
        # are "older" than those listed later in the CFF file
        old_authors: list[dict] = cff["authors"]
        for i, author_a in enumerate(old_authors):
            author_a_identifier = self.create_identifier_of_cff_author_for_warning(
                cff_author=author_a
            )
            for j in range(i + 1, len(old_authors)):
                author_b = old_authors[j]
                if self.is_same_cff_author(
                    cff_author_a=author_a, cff_author_b=author_b
                ):
                    author_b_identifier = (
                        self.create_identifier_of_cff_author_for_warning(
                            cff_author=author_b
                        )
                    )
                    duplication_message: str = (
                        f"The original CFF file has these duplicate authors: {author_a_identifier} and {author_b_identifier}"
                    )

                    warnings.append(duplication_message)
                    if duplicate_author_invalidates_pr:
                        raise Exception(duplication_message)

    def update_cff(
        self,
        contributors: set,
        token: str,
        repo: str,
        pr_number: str,
        output_file: str,
        repo_for_compare: str,
        contribution_details: dict,
    ) -> set:
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
        self.validate_old_cff_authors_are_unique(
            cff=cff,
            warnings=warnings,
            duplicate_author_invalidates_pr=Flags.has(
                "duplicate_author_invalidates_pr"
            ),
        )

        # update new authors
        already_in_cff_contributors: set = set()

        for contributor in contributors:
            new_cff_author: dict | None = None

            contribution_note = self.get_contribution_note_for_warning(
                contributor=contributor,
                contribution_details=contribution_details,
                repo_for_compare=repo_for_compare,
            )

            if isinstance(contributor, GitHubUserContributor):
                new_cff_author = self.create_cff_author_from_github_user_contributor(
                    github_user_contributor=contributor,
                    token=token,
                    contribution_note=contribution_note,
                    warnings=warnings,
                    logs=logs,
                )
            elif isinstance(contributor, GitCommitContributor):
                new_cff_author = self.create_cff_author_from_git_commit_contributor(
                    git_commit_contributor=contributor,
                    cff=cff,
                    contribution_note=contribution_note,
                    warnings=warnings,
                    logs=logs,
                )
            else:
                raise Exception("Invalid contributor class.")

            if new_cff_author is None:
                continue
            else:
                if any(
                    self.is_same_cff_author(existing_cff_author, new_cff_author)
                    for existing_cff_author in cff["authors"]
                ):
                    identifier: str = self.create_identifier_of_cff_author_for_warning(
                        cff_author=new_cff_author
                    )
                    already_in_cff_contributors.add(contributor)
                    warnings.append(f"- {identifier}: Already exists in CFF file.")
                    continue

            cff["authors"].append(new_cff_author)

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
            )

        return missing_authors

    def create_json_for_contribution_details(self, contribution_details: dict) -> str:
        normalized = []
        for contributor, contributions in contribution_details.items():
            normalized_contributor = {
                "contributor": contributor.to_dict(),
                "contributions": contributions,
            }
            normalized.append(normalized_contributor)
        return json.dumps(normalized)
