import logging
import re
from typing import cast

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class OrcidManager:

    def __init__(self):
        self.user_agent = "cff-author-updater"

    @staticmethod
    def extract_orcid(text: str, return_url: bool = True):
        if not text:
            return None
        match = re.search(r"https?://orcid\.org/(\d{4}-\d{4}-\d{4}-\d{4})", text)
        if not match:
            return None
        orcid_id = match.group(1)
        if return_url:
            return f"https://orcid.org/{orcid_id}"
        return orcid_id

    def scrape_orcid_from_github_profile(self, github_username) -> str | None:
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
            details = cast(Tag | None, soup.find("ul", class_=re.compile(r"vcard-details")))

            if details is None:
                logger.info(f"No vcard-details section found for @{github_username}")
                return None

            # Step 2: Look for ORCID link in this section only
            orcid_link = cast(Tag | None, details.find("a", href=re.compile(r"https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{4}")))
            
            if orcid_link:
                href_value = orcid_link.get("href")
                if isinstance(href_value, str):
                    linked_orcid = href_value
                    logger.info(f"Linked ORCID badge for @{github_username}: {linked_orcid}")
                    return linked_orcid
                else:
                    logger.warning(f"ORCID link href is not a string for @{github_username}: {href_value!r}")
                    return None
            else:
                logger.info(f"No linked ORCID badge in vcard-details for @{github_username}")

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch profile for @{github_username}: {e}")

        return None

    def validate_orcid(self, orcid: str):
        if not orcid or not re.match(r"^\d{4}-\d{4}-\d{4}-\d{4}$", orcid):
            return False
        url = f"https://pub.orcid.org/v3.0/{orcid}"
        headers = {"Accept": "application/json"}
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def search_orcid(self, full_name: str, email: str | None = None):
        headers: dict = {"Accept": "application/vnd.orcid+json"}
        name_parts: list[str] = full_name.strip().split(" ", 1)
        given: str = name_parts[0] if len(name_parts) > 0 else ""
        family: str = name_parts[1] if len(name_parts) > 1 else ""
        query: str = f"given-names:{given}"
        if family:
            query += f" AND family-name:{family}"
        if email:
            query += f' OR email:"{email}"'
        url = f"https://pub.orcid.org/v3.0/search/?q={query}"

        try:
            resp: requests.Response = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            results = resp.json()
            if "result" in results and results["result"]:
                match = results["result"][0]
                orcid_id: str = match["orcid-identifier"]["path"]
                rec_url: str = f"https://pub.orcid.org/v3.0/{orcid_id}/personal-details"
                rec_resp: requests.Response = requests.get(
                    rec_url, headers=headers, timeout=5
                )
                rec_resp.raise_for_status()
                details = rec_resp.json()

                credit_name = details.get("credit-name", {}).get("value", "")
                other_names = [
                    n["content"]
                    for n in details.get("other-names", {}).get("other-name", [])
                ]
                given_name: str = details.get("given-names", {}).get("value", "")
                family_name: str = details.get("family-name", {}).get("value", "")
                combined: str = f"{given_name} {family_name}".strip()

                target: str = full_name.strip().casefold()
                possibilities = (
                    [credit_name.strip().casefold()]
                    + [n.strip().casefold() for n in other_names]
                    + [combined.casefold()]
                )
                if target in possibilities:
                    logger.info(
                        f"`{full_name}` matched to ORCID `{orcid_id}` (record name: **{credit_name or combined}**)"
                    )
                    return orcid_id
                else:
                    logger.warning(
                        f"`{full_name}`: ORCID `{orcid_id}` found but name mismatch"
                    )
        except Exception as e:
            logger.warning(f"`{full_name}`: ORCID search failed: {e}")
        return None
