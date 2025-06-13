import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import backoff
import requests
from ratelimit import limits, sleep_and_retry

from . import config

# --- Constants are now in config.py ---
CALLS_PER_MINUTE = 90
ONE_MINUTE = 60


@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=ONE_MINUTE)
@backoff.on_exception(
    backoff.expo, requests.exceptions.RequestException, max_tries=3, max_time=60
)
def make_api_request(url: str, headers: dict, params: dict = None) -> dict:
    """Makes a rate-limited and resilient API request and returns the JSON."""
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def get_puuid_by_riot_id(api_key: str, riot_id: str, tag_line: str) -> str | None:
    """Gets a user's PUUID using their Riot ID (game name + tag line)."""
    try:
        # The regional routing value for the Americas is 'americas'
        account_url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{riot_id}/{tag_line}"
        headers = {"X-Riot-Token": api_key}
        
        print(f"Fetching PUUID for {riot_id}#{tag_line}...")
        account_data = make_api_request(account_url, headers=headers)
        
        puuid = account_data.get("puuid")
        if puuid:
            print(f"PUUID found: {puuid}")
            return puuid
        else:
            print("PUUID not found in the response.")
            return None
            
    except requests.exceptions.RequestException as e:
        # Specifically handle 404 Not Found
        if e.response and e.response.status_code == 404:
            print(f"Riot ID {riot_id}#{tag_line} not found.")
        else:
            print(f"An error occurred calling the Riot API: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def get_matches_played_today(api_key: str, puuid: str) -> int:
    """
    Gets the number of matches played today by fetching match IDs since the
    start of the day (midnight) in the user's local timezone. This logic
    is designed to replicate the JavaScript:
    
    let f = new Date(Date.now());
    f.setHours(0,0,0,0);
    Math.floor(f.getTime() / 1000);
    """
    try:
        # Get the current time in the script's local timezone.
        now = datetime.now()
        # Set the time to exactly midnight.
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        # Convert to a Unix timestamp in seconds, which the API requires.
        start_time_unix = int(start_of_day.timestamp())

        match_ids_url = f"{config.RIOT_API_BASE_URL}/lol/match/v5/matches/by-puuid/{puuid}/ids"
        headers = {"X-Riot-Token": api_key}
        
        # Use the startTime parameter instead of 'count' and looping.
        params = {"startTime": start_time_unix}

        print(f"Fetching match IDs since {start_time_unix}...")
        match_ids = make_api_request(match_ids_url, headers=headers, params=params)
        print(f"Matches returned by the API: {match_ids}")

        # The number of matches is simply the length of the returned list.
        match_count = len(match_ids)
        
        return match_count

    except requests.exceptions.RequestException as e:
        print(f"An error occurred calling the Riot API: {e}")
        # Return 0 on API error to prevent faulty interventions.
        return 0
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        # Return 0 on other errors.
        return 0


def get_match_ids_by_puuid(api_key: str, puuid: str, count: int = 1) -> list | None:
    """Gets a list of the most recent match IDs for a given PUUID."""
    try:
        match_ids_url = f"{config.RIOT_API_BASE_URL}/lol/match/v5/matches/by-puuid/{puuid}/ids"
        headers = {"X-Riot-Token": api_key}
        params = {"count": count}
        
        print(f"Fetching last {count} match IDs for PUUID {puuid}...")
        match_ids = make_api_request(match_ids_url, headers=headers, params=params)
        return match_ids

    except requests.exceptions.RequestException as e:
        print(f"An error occurred calling the Riot API for match IDs: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def get_match_details_by_id(api_key: str, match_id: str) -> dict | None:
    """Gets the details for a specific match ID."""
    try:
        match_details_url = f"{config.RIOT_API_BASE_URL}/lol/match/v5/matches/{match_id}"
        headers = {"X-Riot-Token": api_key}
        
        print(f"Fetching details for match {match_id}...")
        match_details = make_api_request(match_details_url, headers=headers)
        return match_details

    except requests.exceptions.RequestException as e:
        print(f"An error occurred calling the Riot API for match details: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def get_match_timeline_by_id(api_key: str, match_id: str) -> dict | None:
    """Gets the timeline for a specific match ID."""
    try:
        match_timeline_url = f"{config.RIOT_API_BASE_URL}/lol/match/v5/matches/{match_id}/timeline"
        headers = {"X-Riot-Token": api_key}
        
        print(f"Fetching timeline for match {match_id}...")
        match_timeline = make_api_request(match_timeline_url, headers=headers)
        return match_timeline

    except requests.exceptions.RequestException as e:
        print(f"An error occurred calling the Riot API for match timeline: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


# --- Test Execution ---
if __name__ == "__main__":
    from dotenv import load_dotenv

    # Force a reload of the .env file, overwriting any cached variables in the environment.
    load_dotenv(override=True)
    
    test_api_key = os.getenv("RIOT_API_KEY")
    test_puuid = os.getenv("RIOT_PUUID")

    if test_api_key and test_puuid:
        print("--- Testing Riot API Integration (Live) ---")
        match_count = get_matches_played_today(test_api_key, test_puuid)
        if match_count != -1:
            print(f"\\n[SUCCESS] Found {match_count} matches played today.")
        else:
            print("\\n[FAILURE] The API call failed.")
    else:
        print("Please set RIOT_API_KEY and RIOT_PUUID in your .env file to test.") 