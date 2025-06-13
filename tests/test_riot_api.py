import pytest
from unittest.mock import Mock
from src.job_commando.riot_api import get_matches_played_today, RIOT_API_BASE_URL
import requests

# --- Test Data ---
TEST_PUUID = "TEST_PUUID_123"
TEST_API_KEY = "TEST_API_KEY_XYZ"

def test_get_matches_played_today_success(mocker):
    """
    Tests that the function correctly returns the number of matches
    when the Riot API call is successful.
    """
    # Arrange: Mock the requests.get call
    mock_response = Mock()
    expected_matches = ["NA1_123", "NA1_456", "NA1_789"]
    mock_response.json.return_value = expected_matches
    mock_response.raise_for_status.return_value = None  # Do nothing when called
    mocker.patch('requests.get', return_value=mock_response)

    # Act: Call the function we are testing
    match_count = get_matches_played_today(TEST_API_KEY, TEST_PUUID)

    # Assert: Verify the result
    assert match_count == len(expected_matches)
    # Also assert that requests.get was called with the correct URL and params
    requests.get.assert_called_once()
    call_args = requests.get.call_args
    assert call_args.args[0] == f"{RIOT_API_BASE_URL}/lol/match/v5/matches/by-puuid/{TEST_PUUID}/ids"
    assert "startTime" in call_args.kwargs['params']


def test_get_matches_played_today_api_error(mocker):
    """
    Tests that the function returns -1 when the Riot API returns an error.
    """
    # Arrange: Mock the requests.get call to simulate an HTTP error
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Client Error: Forbidden")
    mocker.patch('requests.get', return_value=mock_response)

    # Act: Call the function
    match_count = get_matches_played_today(TEST_API_KEY, TEST_PUUID)

    # Assert: Verify it returns our error code
    assert match_count == -1 