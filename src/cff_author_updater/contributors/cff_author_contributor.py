
from __future__ import annotations

from cff_author_updater.contributors.contributor import Contributor
from cff_author_updater.contributors.github_contributor import (
    is_github_user_profile_url,
)


class CffAuthorContributor(Contributor):

    def __init__(self, cff_author_data: dict):
        super().__init__()

        if isinstance(cff_author_data, dict) is False:
            raise ValueError(f"Invalid CFF author data: {cff_author_data}")

        self.cff_author_data = cff_author_data
        self.author_type = self._get_author_type(cff_author_data=self.cff_author_data)

        self.id = self._get_id_from_cff_author_data(
            cff_author_data=self.cff_author_data
        )

    def to_dict(self) -> dict:
        """
        Convert the CFF Author Contributor to a serializable dictionary representation.
        """
        return {
            "cff_author_data": self.cff_author_data,
            "author_type": self.author_type,
            "id": self.id,
        }

    def _get_author_type(self, cff_author_data):
        # determine CFF author type
        if "name" in cff_author_data:
            return "entity"
        elif "given-names" in cff_author_data and "family-names" in cff_author_data:
            return "person"
        else:
            raise ValueError(f"Unknown CFF Author Type {cff_author_data}")

    def _get_id_from_cff_author_data(self, cff_author_data: dict) -> str:
        if "orcid" in cff_author_data:
            return cff_author_data["orcid"]
        elif "alias" in cff_author_data and is_github_user_profile_url(
            cff_author_data["alias"]
        ):
            return cff_author_data["alias"]
        elif "email" in cff_author_data:
            return cff_author_data["email"]
        elif "given-names" in cff_author_data and "family-names" in cff_author_data:
            return (
                cff_author_data["given-names"] + " " + cff_author_data["family-names"]
            )
        elif "name" in cff_author_data:
            return cff_author_data["name"]
        else:
            raise ValueError(f"Invalid CFF author data {cff_author_data}")

    def is_same_author(self, cff_author: CffAuthorContributor):
        a: dict = self.cff_author_data
        b: dict = cff_author.cff_author_data

        a_type: str = self.author_type
        b_type: str = cff_author.author_type

        if a_type == "unknown" or b_type == "unknown":
            raise ValueError("Cannot compare unknown author types.")

        # Match in the following order (case-insensitive and surrounding whitespace insensitive):
        # 1. orcid
        # 2. alias (only using GitHub user profile URL)
        # 3. email
        # 4. full name (using given-names + ' ' + family-names if type person, or 'name' that has at least two parts if type is entity)

        # match orcid
        a_orcid = a.get("orcid", "").casefold().strip()
        b_orcid = b.get("orcid", "").casefold().strip()
        if a_orcid and a_orcid == b_orcid:
            return True

        # else match on alias if and only if it's a GitHub user profile URL
        a_alias = a.get("alias", "").casefold().strip()
        b_alias = b.get("alias", "").casefold().strip()
        a_is_github_user = is_github_user_profile_url(url=a_alias)
        if a_alias and b_alias == b_alias and a_is_github_user:
            return True

        # else, match on email
        a_email = a.get("email", "").casefold().strip()
        b_email = b.get("email", "").casefold().strip()
        if a_email and a_email == b_email:
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
                "Cannot compare a CFF author that lacks an ORCID, email, alias, and name."
            )

        if a_fullname == b_fullname:
            return True
        else:
            return False
