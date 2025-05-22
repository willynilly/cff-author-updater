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
        # Ensure comparison is between same types
        if a.get("type") != b.get("type"):
            return False

        if a["type"] == "entity":
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

    # normalize authors
    def normalize_authors(self, authors: list[dict]):
        n_authors = []
        for author in authors:
            if "type" in author:
                del author["type"]
                n_authors.append(author)
        return n_authors

    def process_contributors(
        self,
        contributors,
        cff_path,
        token,
        repo,
        pr_number,
        output_file,
        flags,
        contributor_metadata,
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
            sha_note: str = f" (commit: `{sha[:7]}`)" if sha else ""

            if isinstance(contributor, str):
                user_url: str = f"https://api.github.com/users/{contributor}"
                resp: requests.Response = requests.get(
                    user_url, headers={"Authorization": f"token {token}"}
                )
                if resp.status_code != 200:
                    continue
                user = resp.json()
                user_type = user.get("type")

                if user_type == "Organization":
                    entry["name"] = user.get("name") or contributor
                    entry["alias"] = contributor
                    entry["type"] = "entity"
                    if user.get("email"):
                        entry["email"] = user["email"]
                else:
                    full_name: str = user.get("name") or contributor
                    name_parts: list[str] = full_name.split(" ", 1)

                    if len(name_parts) > 1:
                        entry["given-names"] = name_parts[0]
                        entry["family-names"] = name_parts[1]
                        entry["alias"] = contributor
                        entry["type"] = "person"
                    else:
                        entry["name"] = full_name
                        entry["alias"] = contributor
                        entry["type"] = "entity"
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

                identifier: str = contributor.casefold()

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
                    entry["type"] = "entity"
                else:
                    if len(name_parts) > 1:
                        entry["given-names"] = name_parts[0]
                        entry["family-names"] = name_parts[1]
                        if email:
                            entry["email"] = email
                        entry["type"] = "person"
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
                        entry["type"] = "entity"
                        warnings.append(
                            f"- `{full_name}`: Only one name part found, treated as entity for deduplication consistency.{sha_note}"
                        )

                identifier = email or name.casefold()

            if any(self.is_same_person(a, entry) for a in cff["authors"]):
                warnings.append(f"- {identifier}: Already exists in CFF file.")
                continue

            cff["authors"].append(entry)
            new_users.append(identifier)

        cff["authors"] = self.normalize_authors(cff["authors"])

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
                new_users, cff_path, cff, warnings, logs, token, repo, pr_number
            )
