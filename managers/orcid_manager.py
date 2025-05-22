import re

import requests


class OrcidManager:

    def __init__(self):
        pass

    def extract_orcid(self, text: str):
        if not text:
            return None
        match = re.search(r"https?://orcid\.org/(\d{4}-\d{4}-\d{4}-\d{4})", text)
        return match.group(1) if match else None

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

    def search_orcid(
        self, full_name: str, email: str | None = None, logs: list | None = None
    ):
        headers: dict = {"Accept": "application/vnd.orcid+json"}
        name_parts: list[str] = full_name.strip().split(" ", 1)
        given: str = name_parts[0]
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
                    log = f"- `{full_name}` matched to ORCID `{orcid_id}` (record name: **{credit_name or combined}**)"
                    if logs is not None:
                        logs.append(log)
                    return orcid_id
                else:
                    if logs is not None:
                        logs.append(
                            f"- `{full_name}`: ORCID `{orcid_id}` found but name mismatch"
                        )
        except Exception as e:
            if logs is not None:
                logs.append(f"- `{full_name}`: ORCID search failed: {e}")
        return None
