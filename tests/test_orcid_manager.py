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
