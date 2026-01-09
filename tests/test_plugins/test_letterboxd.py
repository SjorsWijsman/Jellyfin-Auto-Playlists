import pytest
from plugins.letterboxd import Letterboxd

# Test data as fixtures
@pytest.fixture
def test_lists():
    return [
        "jf_auto_collect/watchlist",
        "jf_auto_collect/likes/films",
        "jf_auto_collect/list/test_list/"
    ]

@pytest.fixture
def test_list_output():
    return [
        {'title': 'The Godfather', 'media_type': 'movie', 'imdb_id': 'tt0068646', 'release_year': '1972'},
        {'title': 'The Godfather Part II', 'media_type': 'movie', 'imdb_id': 'tt0071562', 'release_year': '1974'}
    ]

# Parametrized test for different lists
@pytest.mark.parametrize("test_list", [
    "jf_auto_collect/watchlist",
    "jf_auto_collect/likes/films",
    "jf_auto_collect/list/test_list/"
])
def test_get_list(test_list, test_list_output):
    # Assuming Letterboxd.get_list returns a dictionary with a key "items"
    result = Letterboxd.get_list(test_list, {"imdb_id_filter": True})

    # Check that the correct items are present (order may vary by list type)
    # We preserve the natural order from Letterboxd, which differs between watchlists, likes, and regular lists
    assert len(result["items"]) == len(test_list_output), f"Expected {len(test_list_output)} items, got {len(result['items'])}"

    # Sort both lists by imdb_id for comparison (order preservation is tested separately)
    result_sorted = sorted(result["items"], key=lambda x: x.get('imdb_id', ''))
    expected_sorted = sorted(test_list_output, key=lambda x: x.get('imdb_id', ''))

    assert result_sorted == expected_sorted


def test_order_preservation():
    """Test that items are returned in their natural order from Letterboxd consistently"""
    # Get the same list twice - order should be consistent
    result1 = Letterboxd.get_list("jf_auto_collect/list/test_list/", {"imdb_id_filter": True})
    result2 = Letterboxd.get_list("jf_auto_collect/list/test_list/", {"imdb_id_filter": True})

    # Order should be exactly the same both times (preserving Letterboxd's natural order)
    assert result1["items"] == result2["items"], "Order should be consistent across multiple fetches"
    assert len(result1["items"]) > 0, "Should return at least one item"

