from cff_author_updater.managers.orcid_manager import OrcidManager


def test_search_orcid_with_valid_name_and_email_for_public_name_and_private_email():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()
    
    name = "Will Riley"
    email = "wanderingwill@gmail.com"

    orcids: list[str] = orcid_manager.search_orcid(name=name, email=email, return_url=True)

    expected_orcids = []
    assert orcids == expected_orcids

def test_search_orcid_with_only_valid_name_for_public_name_and_private_email():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()
    
    name = "Will Riley"

    orcids: list[str] = orcid_manager.search_orcid(name=name, return_url=True)

    expected_orcids = ["https://orcid.org/0000-0003-1822-6756"]
    assert all(x in orcids for x in expected_orcids), f"Expected {expected_orcids} but got {orcids}"

def test_scrape_orcid_from_github_profile_with_valid_github_username_and_orcid_in_profile_badge():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    github_username: str = "willynilly"
    orcid: str | None = orcid_manager.scrape_orcid_from_github_profile(github_username=github_username)
    expected_orcid: str | None = "https://orcid.org/0000-0003-1822-6756"
    assert orcid == expected_orcid, f"Expected {expected_orcid} but got {orcid}"

def test_scrape_orcid_from_github_profile_with_valid_github_username_and_orcid_not_in_profile():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    github_username: str = "estelle-ruby"
    orcid: str | None = orcid_manager.scrape_orcid_from_github_profile(github_username=github_username)
    expected_orcid: str | None = None
    assert orcid == expected_orcid, f"Expected {expected_orcid} but got {orcid}"

def test_get_names_from_orcid_with_valid_orcid():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    orcid: str = "0000-0003-1822-6756"
    names, credit_name, combined_credit_name, other_names = orcid_manager.get_names_from_orcid(orcid=orcid, is_url=False)

    expected_names = ['Will Riley', 'William Fowler Riley III', 'Willy Riley']
    assert names == expected_names, f"Expected {expected_names} but got {names}"

    expected_credit_name = "Will Riley"
    assert credit_name == expected_credit_name, f"Expected {expected_credit_name} but got {credit_name}"

    expected_combined_credit_name = "Will Riley"
    assert combined_credit_name == expected_combined_credit_name, f"Expected {expected_combined_credit_name} but got {combined_credit_name}"

    expected_other_names = ['William Fowler Riley III', 'Willy Riley']
    assert other_names == expected_other_names, f"Expected {expected_other_names} but got {other_names}"

def test_validate_orcid_with_valid_orcid_id():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    orcid: str = "0000-0003-1822-6756"
    is_valid: bool = orcid_manager.validate_orcid(orcid=orcid, is_url=False)

    assert is_valid, f"Expected ORCID {orcid} to be valid but it was not."

def test_validate_orcid_with_invalid_orcid_id():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    orcid: str = "00000-0003-1822-6756"
    is_valid: bool = orcid_manager.validate_orcid(orcid=orcid, is_url=False)

    assert not is_valid, f"Expected ORCID {orcid} to be invalid but it was valid."

def test_validate_orcid_with_valid_orcid_url():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    orcid_id: str = "0000-0003-1822-6756"
    orcid = f"https://orcid.org/{orcid_id}"
    is_valid: bool = orcid_manager.validate_orcid(orcid=orcid, is_url=True)

    assert is_valid, f"Expected ORCID {orcid} to be valid but it was not."

def test_validate_orcid_with_invalid_orcid_url():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    orcid_id: str = "00000-0003-1822-6756"
    orcid = f"https://orcid.org/{orcid_id}"
    is_valid: bool = orcid_manager.validate_orcid(orcid=orcid, is_url=True)

    assert not is_valid, f"Expected ORCID {orcid} to be invalid but it was valid."

def test_extract_orcid_from_text_with_valid_orcid_url():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    expected_orcid = "https://orcid.org/0000-0003-1822-6756"

    text = f"This is a test text with an ORCID: {expected_orcid}. And this is some additional text."
    orcid = orcid_manager.extract_orcid(text=text, return_url=True)

    assert orcid == expected_orcid, f"Expected {expected_orcid} but got {orcid}"

def test_extract_first_orcid_from_text_with_two_valid_orcid_urls():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    expected_orcid = "https://orcid.org/0000-0003-1822-6756"
    another_valid_orcid = "https://orcid.org/0000-0003-1822-6758"

    text = f"This is a test text with an ORCID: {expected_orcid}. Here's another ORCID: {another_valid_orcid}. And this is some additional text."
    orcid = orcid_manager.extract_orcid(text=text, return_url=True)

    assert orcid == expected_orcid, f"Expected {expected_orcid} but got {orcid}"

def test_extract_orcid_from_text_with_invalid_orcid_url():
    orcid_manager = OrcidManager()
    orcid_manager.clear_cache()

    text = "This is a test text with an ORCID: https://orcid.org/00000-0003-1822-6756. And this is some additional text."
    orcid = orcid_manager.extract_orcid(text=text, return_url=True)

    expected_orcid = None
    assert orcid == expected_orcid, f"Expected {expected_orcid} but got {orcid}"
