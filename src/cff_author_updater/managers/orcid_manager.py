import logging
from functools import lru_cache
from typing import cast

import regex
import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class OrcidManager:

    

    ORCID_URL_PATTERN = regex.compile(
        r"https://orcid\.org/(?P<orcid_id>\d{4}-\d{4}-\d{4}-\d{3}[\dX])",
        flags=regex.UNICODE | regex.IGNORECASE
    )

    ORCID_ID_PATTERN_FOR_EXTRACT = regex.compile(
        r"\b(?P<orcid_id>\d{4}-\d{4}-\d{4}-\d{3}[\dX])\b",
        flags=regex.UNICODE
    )


    SCRAPE_ORCID_BADGE_PATTERN = regex.compile(r"vcard-details", flags=regex.UNICODE)

    ORCID_ID_FOR_VALIDATE_PATTERN = regex.compile(r"^(?P<orcid_id>\d{4}-\d{4}-\d{4}-\d{3}[\dX])$", flags=regex.UNICODE)


    def __init__(self):
        self.user_agent = "cff-author-updater"

    @staticmethod
    def extract_orcid(text: str, find_url: bool = True, return_url: bool = True):
        if not text:
            return None
        

        if find_url:
            match = OrcidManager.ORCID_URL_PATTERN.search(text)
        else:
            match = OrcidManager.ORCID_ID_PATTERN_FOR_EXTRACT.search(text)
        
        if not match:
            return None

        orcid_id = match.group("orcid_id")

        if return_url:
            url = f"https://orcid.org/{orcid_id}"
            return url.casefold()

        return orcid_id


    @lru_cache(maxsize=None, typed=True)
    def scrape_orcid_from_github_profile(self, github_username: str) -> str | None:
        """Scrape linked ORCID badge from GitHub profile using BeautifulSoup."""
        url = f"https://github.com/{github_username}"
        headers = {
            "User-Agent": self.user_agent
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            html = response.text

            soup = BeautifulSoup(html, "html.parser")

            # Step 1: Find the profile details section
            details = cast(Tag | None, soup.find(
                "ul",
                class_=lambda cls: bool(cls) and bool(OrcidManager.SCRAPE_ORCID_BADGE_PATTERN.search(cls))
            ))

            if details is None:
                logger.info(f"No vcard-details section found for @{github_username}")
                return None

            # Step 2: Look for ORCID link in this section only
            orcid_link = cast(Tag | None, details.find("a", href=lambda href: bool(OrcidManager.ORCID_URL_PATTERN.match(href or ""))))
            
            if orcid_link:
                href_value = orcid_link.get("href")
                if isinstance(href_value, str):
                    linked_orcid = href_value
                    logger.info(f"Linked ORCID badge for @{github_username}: {linked_orcid}")
                    return linked_orcid
                else:
                    logger.warning(f"ORCID link href is not a string for @{github_username}: {href_value!r}")
            else:
                logger.info(f"No linked ORCID badge on GitHub profile page for @{github_username}")

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch GitHub profile for @{github_username}: {e}")

        return None

    @lru_cache(maxsize=None, typed=True)
    def validate_orcid(self, orcid: str, is_url: bool = True) -> bool:
        if orcid is None or not isinstance(orcid, str):
            return False

        if not is_url:
            orcid_id = orcid.strip()
        else:
            orcid_id: str | None = self.extract_orcid(text=orcid, find_url=True, return_url=False)
            if orcid_id:
                orcid_id = orcid_id.strip()

        # Validate ORCID id format 

        if not orcid_id or not OrcidManager.ORCID_ID_FOR_VALIDATE_PATTERN.match(orcid_id):
            return False

        url = f"https://pub.orcid.org/v3.0/{orcid_id}"
        headers = {"Accept": "application/json"}

        try:
            resp = requests.get(url, headers=headers, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    
    @lru_cache(maxsize=None, typed=True)
    def search_orcid(self, name: str | None, email: str | None = None, return_url: bool = True) -> list[str]:
        """Search for ORCID IDs based on name and email.
        Args:
            name (str | None): The name of the person to search for.
            email (str | None): The email of the person to search for.
            return_url (bool): Whether to return the full ORCID URL or just the ID.
        Returns:
            list[str]: A list of ORCID IDs matching all of the search criteria.
        """
        logger.debug(f'search_orcid name:{name} email:{email}')
        headers: dict = {"Accept": "application/vnd.orcid+json"}

        query_parts: list[str] = []
        if name:
            name_parts: list[str] = name.strip().split(" ", 1)
            given: str = name_parts[0] if len(name_parts) > 0 else ""
            family: str = name_parts[1] if len(name_parts) > 1 else ""
            if given:
                query_parts.append(f'given-names:"{given}"')

            if family:
                query_parts.append(f'family-name:"{family}"')

        if email:
            query_parts.append(f'email:"{email}"')

        if not query_parts:
            logger.warning("No name or email provided for ORCID search.")
            return []
        

        query: str = " AND ".join(query_parts)

        url = f"https://pub.orcid.org/v3.0/search/?q={query}"

        orcids: list[str] = []

        try:
            resp: requests.Response = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            results = resp.json()
            if "result" in results and results["result"]:
                for result in results["result"]:
                    orcid_id: str = result["orcid-identifier"]["path"]
                    orcid: str | None = orcid_id
                    if return_url:
                        orcid = f"https://orcid.org/{orcid_id}"
                    if name:
                        # Check if the name matches the ORCID record
                        target_name: str = name.strip().casefold()

                        # Fetch names associated with the ORCID ID
                        possible_names, credit_name, combined_credit_name, other_names = self.get_names_from_orcid(orcid=orcid, is_url=return_url)

                        possible_names = [n.strip().casefold() for n in possible_names]

                        if target_name in possible_names:
                            logger.info(
                                f"`{name}` matched to ORCID `{orcid}` (record name: **{credit_name or combined_credit_name}**)"
                            )
                            orcids.append(orcid)
                    elif email:
                        orcids.append(orcid)
                        logger.info(f"`{email}` matched to ORCID `{orcid}` (record name: **{credit_name or combined_credit_name}**)")
        except Exception:
            pass
        logger.info(f"`{name}`: ORCID search failed to find a match.")
        return orcids

    def get_names_from_orcid(self, orcid: str, is_url: bool = True) -> tuple[list[str], str, str, list[str]]:
        """Fetch names associated with a given ORCID ID.
        Args:
            orcid (str): The ORCID ID to look up.
        Returns:
            tuple[list[str], str, str, list[str]]:
                - list[str]: A list of names associated with the ORCID ID.
                - str: The credit name if available.
                - str: The combined given and family name of the credit name if available.
                - list[str]: A list of other names associated with the ORCID ID.
        """
        if is_url:
            orcid_id: str | None = self.extract_orcid(text=orcid, find_url=True, return_url=False)
            if not orcid_id:
                logger.warning(f"Invalid ORCID URL provided: {orcid}")
                return [], '', '', []
        else:
            orcid_id = orcid
        headers: dict = {"Accept": "application/vnd.orcid+json"}
        url = f"https://pub.orcid.org/v3.0/{orcid_id}/personal-details"
        try:
            resp: requests.Response = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            details = resp.json()
            names: list[str] = []
            main_name = details.get("name", {}) or {}

            credit_name: str = (main_name.get("credit-name", {}) or {}).get("value", "").strip()
            given_name: str = (main_name.get("given-names", {}) or {}).get("value", "").strip()
            family_name: str = (main_name.get("family-name", {}) or {}).get("value", "").strip()
            
            if credit_name and credit_name not in names:
                names.append(credit_name)

            if given_name and family_name:
                combined_credit_name: str = f"{given_name} {family_name}".strip()
                if combined_credit_name and combined_credit_name not in names:
                    names.append(combined_credit_name)

            other_names: list[str] = []
            for other in (details.get("other-names", {}) or {}).get("other-name", []):
                other_name = other.get("content", "").strip()
                if other_name:
                    if other_name not in other_names:
                        other_names.append(other_name)
                    if other_name not in names:
                        names.append(other_name)

            return names, credit_name, combined_credit_name, other_names
        except Exception:
            return [], '', '', []  # Return empty names if the request fails

    def clear_cache(self):
        self.search_orcid.cache_clear()
        self.scrape_orcid_from_github_profile.cache_clear()
        self.validate_orcid.cache_clear()
