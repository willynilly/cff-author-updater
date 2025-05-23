from pathlib import Path
import requests
import yaml

from managers.github_manager import GithubManager
from managers.orcid_manager import OrcidManager


class CffManager:

    def __init__(self, github_manager: GithubManager, orcid_manager: OrcidManager):
        self.github_manager = github_manager
        self.orcid_manager = orcid_manager

    def validate_cff(self, cff_path: str):
        import subprocess

        try:
            subprocess.run(
                ["cffconvert", "--validate", "--infile", cff_path], check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def is_same_person(self, a: dict, b: dict):
        a_type: str = self.get_cff_author_type(a)
        b_type: str = self.get_cff_author_type(b)

        if a_type == "unknown" or b_type == "unknown":
            raise ValueError("Cannot compare unknown author types.")

        # Ensure comparison is between same types
        if a_type != b_type:
            return False

        if a_type == "entity":
            return (
                a.get("name", "").strip().casefold()
                == b.get("name", "").strip().casefold()
            )

        return (
            a.get("alias", "").casefold() == b.get("alias", "").casefold()
            or a.get("email", "").casefold() == b.get("email", "").casefold()
            or a.get("orcid", "").casefold() == b.get("orcid", "").casefold()
            or (
                f"{a.get('given-names', '').strip().casefold()} {a.get('family-names', '').strip().casefold()}".strip()
                == f"{b.get('given-names', '').strip().casefold()} {b.get('family-names', '').strip().casefold()}".strip()
            )
        )

    def get_cff_author_type(self, author: dict):
        if "name" in author:
            return "entity"
        elif "given-names" in author and "family-names" in author:
            return "person"
        else:
            return "unknown"

    def process_contributors(
        self,
        contributors: set,
        cff_path: str,
        token: str,
        repo: str,
        pr_number: str,
        output_file: str,
        flags: dict,
        contributor_metadata: dict,
    ):
        path: Path = Path(cff_path)
        if not path.exists():
            print(f"{cff_path} not found.")
            return

        if not self.validate_cff(cff_path):
            print(f"Validation failed for input CFF file: {cff_path}")
            return

        with open(path, "r") as f:
            cff = yaml.safe_load(f)

        cff.setdefault("authors", [])

        new_users: list = []
        warnings: list = []
        logs: list = []

        for contributor in contributors:
            entry: dict = {}
            identifier: str = ""
            sha: str = contributor_metadata.get(contributor, {}).get("sha", "")
            sha_note: str = (
                f" (commit: [`{sha[:7]}`](https://github.com/{repo}/commit/{sha}))"
                if sha
                else ""
            )

            if isinstance(contributor, str):
                # Github user contributor
                identifier: str = contributor.casefold()
                user_url: str = f"https://api.github.com/users/{contributor}"
                resp: requests.Response = requests.get(
                    user_url, headers={"Authorization": f"token {token}"}
                )

                # skip the user if the user is not found
                if resp.status_code != 200:
                    warnings.append(
                        f"- @{contributor}: Unable to fetch user data from GitHub API. Status code: {resp.status_code}{sha_note}"
                    )
                    continue

                # determine the type of user
                user = resp.json()
                user_type = user.get("type")

                if user_type == "Organization":
                    entry["name"] = user.get("name") or contributor
                    entry["alias"] = contributor
                    if user.get("email"):
                        entry["email"] = user["email"]
                else:
                    full_name: str = user.get("name") or contributor
                    name_parts: list[str] = full_name.split(" ", 1)

                    if len(name_parts) > 1:
                        entry["given-names"] = name_parts[0]
                        entry["family-names"] = name_parts[1]
                        entry["alias"] = contributor
                    else:
                        entry["name"] = full_name
                        entry["alias"] = contributor
                        warnings.append(
                            f"- @{contributor}: Only one name part found, treated as entity for deduplication consistency.{sha_note}"
                        )
                        if any(self.is_same_person(a, entry) for a in cff["authors"]):
                            warnings.append(
                                f"- {identifier}: Already exists in CFF file."
                            )
                            continue
                        cff["authors"].append(entry)
                        new_users.append(identifier)
                        continue

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
                            f"- @{contributor}: ORCID `{orcid}` is invalid or unreachable."
                        )
                    else:
                        warnings.append(f"- @{contributor}: No ORCID found.")

            else:
                name, email = contributor
                name_parts: list[str] = name.split(" ", 1)
                full_name: str = name
                entry_type: str = "entity"
                matched: bool = False

                for existing in cff["authors"]:
                    if (
                        "given-names" in existing
                        and "family-names" in existing
                        and "email" in existing
                    ):
                        existing_name = f"{existing['given-names']} {existing['family-names']}".strip().casefold()
                        if (
                            existing_name == name.strip().casefold()
                            and existing["email"].strip().casefold()
                            == email.strip().casefold()
                        ):
                            entry["given-names"] = existing["given-names"]
                            entry["family-names"] = existing["family-names"]
                            entry["email"] = existing["email"]
                            if "orcid" in existing:
                                entry["orcid"] = existing["orcid"]
                            entry_type = "person"
                            matched = True
                            break

                if entry_type == "entity" and not matched:
                    if not name.strip():
                        warnings.append(
                            f"- Commit author with email `{email}` has no name and was skipped.{sha_note}"
                        )
                        continue
                    entry["name"] = name
                    if email:
                        entry["email"] = email
                else:
                    if len(name_parts) > 1:
                        entry["given-names"] = name_parts[0]
                        entry["family-names"] = name_parts[1]
                        if email:
                            entry["email"] = email
                        orcid = self.orcid_manager.search_orcid(full_name, email, logs)
                        if orcid and self.orcid_manager.validate_orcid(orcid):
                            entry["orcid"] = f"https://orcid.org/{orcid}"
                        elif orcid:
                            warnings.append(
                                f"- `{full_name}`: ORCID `{orcid}` is invalid or unreachable."
                            )
                        else:
                            warnings.append(f"- `{full_name}`: No ORCID found.")
                    else:
                        entry["name"] = full_name
                        if email:
                            entry["email"] = email
                        warnings.append(
                            f"- `{full_name}`: Only one name part found, treated as entity for deduplication consistency.{sha_note}"
                        )

                identifier = email or name.casefold()

            if any(self.is_same_person(a, entry) for a in cff["authors"]):
                warnings.append(f"- {identifier}: Already exists in CFF file.")
                continue

            cff["authors"].append(entry)
            new_users.append(identifier)

        with open(cff_path, "w") as f:
            yaml.dump(cff, f, sort_keys=False)

        if not self.validate_cff(cff_path):
            print(f"Validation failed for output CFF file: {cff_path}")
            return

        with open(output_file, "a") as f:
            f.write(f"new_users={','.join(new_users)}\n")
            f.write("updated_cff<<EOF\n")
            f.write(yaml.dump(cff, sort_keys=False))
            f.write("\nEOF\n")
            if warnings:
                f.write("warnings<<EOF\n" + "\n".join(warnings) + "\nEOF\n")
            if logs:
                f.write("orcid_logs<<EOF\n" + "\n".join(logs) + "\nEOF\n")

        if flags["post_comment"] and pr_number:
            self.github_manager.post_pull_request_comment(
                new_users=new_users,
                cff_path=cff_path,
                cff=cff,
                warnings=warnings,
                logs=logs,
                token=token,
                repo=repo,
                pr_number=pr_number,
            )
