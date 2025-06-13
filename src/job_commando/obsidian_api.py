import requests
from datetime import datetime, timedelta
import os
import urllib3
import re

from . import config

# --- Suppress InsecureRequestWarning ---
# This is necessary because we are using a self-signed certificate for the
# Obsidian Local REST API. We are accepting this known risk for this
# specific, local-only connection.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# --- Certificate Path Correction ---
# Build an absolute path to the certificate from the project root.
# This assumes the script is run from the project's root directory,
# which is standard for Flask applications.
CERT_PATH = os.path.abspath("private/obsidian_cert/obsidian-local-rest-api.crt")

def _make_obsidian_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """
    A centralized helper function for making requests to the Obsidian Local REST API.
    It handles URL construction, headers, certificate verification, and error handling.
    """
    url = f"{config.OBSIDIAN_API_BASE_URL}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {config.OBSIDIAN_API_KEY}",
        **kwargs.pop("headers", {})  # Allow for additional headers
    }
    
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            verify=CERT_PATH,
            **kwargs
        )
        response.raise_for_status()
        return response
    except requests.exceptions.SSLError as e:
        print(f"---! SSL Certificate Error !---")
        print(f"Failed to verify certificate at the constructed path: {CERT_PATH}")
        print(f"Please ensure the certificate exists at 'private/obsidian_cert/obsidian-local-rest-api.crt' relative to your project root.")
        print(f"Current working directory is: {os.getcwd()}")
        print(f"Error details: {e}")
        # Re-raise the exception to stop execution, as this is a critical config error.
        raise
    except requests.exceptions.RequestException as e:
        # For other request errors (connection, timeout), we log and return None.
        print(f"An error occurred calling the Obsidian API: {e}")
        return None

def daily_log_exists(check_date: datetime.date) -> bool:
    """
    Checks if a daily log for a given date exists in the Obsidian vault
    by using the local REST API.

    Args:
        check_date: The date to check for.

    Returns:
        True if the file exists, False otherwise.
    """
    file_path = f"{config.DAILY_LOG_PATH_PREFIX}/{check_date.strftime(config.DATE_FORMAT)}.md"
    response = _make_obsidian_request("GET", f"vault/{file_path}")
    return response is not None and response.status_code == 200

def log_intervention(reason: str, details: str) -> bool:
    """
    Appends a record of an intervention to today's daily log in Obsidian.

    Args:
        reason: The trigger for the intervention (e.g., "League Vortex").
        details: Specifics of the trigger (e.g., "4 matches played").

    Returns:
        True if the log was successfully appended, False otherwise.
    """
    file_path = f"{config.DAILY_LOG_PATH_PREFIX}/{datetime.now().date().strftime(config.DATE_FORMAT)}.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"""
---
### Compassionate Intervention Log
- **Timestamp:** {timestamp}
- **Trigger:** {reason}
- **Details:** {details}
- **Action:** Created a 'Compassionate Check-in' event on Google Calendar.
- **Follow-up:** - [ ] Did we connect?
---
"""
    headers = {"Content-Type": "text/markdown"}
    response = _make_obsidian_request(
        "POST", f"vault/{file_path}", headers=headers, data=log_content.encode('utf-8')
    )
    if response:
        print(f"Successfully appended intervention log to '{file_path}'")
        return True
    print(f"Failed to append to Obsidian log for path '{file_path}'")
    return False

def create_daily_log_with_intervention(reason: str, details: str) -> bool:
    """
    Creates today's daily log file in Obsidian with an intervention record
    as its initial content, using a full daily template.

    Args:
        reason: The trigger for the intervention (e.g., "Radio Silence").
        details: Specifics of the trigger.

    Returns:
        True if the log was successfully created, False otherwise.
    """
    file_path = f"{config.DAILY_LOG_PATH_PREFIX}/{datetime.now().date().strftime(config.DATE_FORMAT)}.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"""---
games_played: 0
marijuana_use: null
swam: false
nutrition: null
sleep_quality: null
---

# Daily Log for {datetime.now().date().strftime('%A, %B %d, %Y')}

### Compassionate Intervention Log
- **Timestamp:** {timestamp}
- **Trigger:** {reason}
- **Details:** {details}
- **Action:** Created a 'Compassionate Check-in' event on Google Calendar.
- **Follow-up:** - [ ] Did we connect?
---

## Win for the Day:

## Main Sticking Point:

## A Moment of Self-Care:

## Key Takeaway:
"""
    headers = {"Content-Type": "text/markdown"}
    response = _make_obsidian_request(
        "PUT", f"vault/{file_path}", headers=headers, data=log_content.encode('utf-8')
    )
    if response:
        print(f"Successfully created daily log with intervention at '{file_path}'")
        return True
    print(f"Failed to create Obsidian log at '{file_path}'")
    return False

def note_contains_string(note_date: datetime.date, search_string: str) -> bool:
    """
    Checks if the daily note for a given date contains a specific string.

    Args:
        note_date: The date of the note to check.
        search_string: The string to search for.

    Returns:
        True if the string is found, False otherwise.
    """
    file_path = f"{config.DAILY_LOG_PATH_PREFIX}/{note_date.strftime(config.DATE_FORMAT)}.md"
    response = _make_obsidian_request("GET", f"vault/{file_path}")
    
    if response is None:
        return False # API call failed
    if response.status_code == 404:
        return False # Note doesn't exist

    return search_string in response.text

def update_games_played_in_daily_log(match_count: int) -> bool:
    """
    Updates the 'games_played' value in the frontmatter of today's daily log.

    Args:
        match_count: The new number of games played.

    Returns:
        True if the update was successful, False otherwise.
    """
    file_path = f"{config.DAILY_LOG_PATH_PREFIX}/{datetime.now().date().strftime(config.DATE_FORMAT)}.md"
    
    # 1. Get the current note content
    response = _make_obsidian_request("GET", f"vault/{file_path}")
    if response is None or response.status_code != 200:
        print(f"Failed to get content of '{file_path}' to update games_played.")
        return False
    
    original_content = response.text
    
    # 2. Update the games_played value using regex
    # This pattern is designed to be safe and only replace the value.
    new_content, num_replacements = re.subn(
        r"^(games_played: ).*$", 
        f"\\g<1>\"{match_count}\"", 
        original_content, 
        flags=re.MULTILINE
    )

    if num_replacements == 0:
        print(f"Warning: 'games_played' key not found in '{file_path}'. Could not update.")
        return False

    # 3. Write the updated content back to the note
    headers = {"Content-Type": "text/markdown"}
    update_response = _make_obsidian_request(
        "PUT", f"vault/{file_path}", headers=headers, data=new_content.encode('utf-8')
    )

    if update_response:
        print(f"Successfully updated games_played to {match_count} in '{file_path}'")
        return True
    
    print(f"Failed to write updated content to '{file_path}'")
    return False

def log_follow_up() -> bool:
    """Appends a gentle follow-up note to today's daily log."""
    file_path = f"{config.DAILY_LOG_PATH_PREFIX}/{datetime.now().date().strftime(config.DATE_FORMAT)}.md"
    follow_up_content = """
---
### Gentle Follow-up
- A 'Compassionate Intervention' was logged yesterday, but the check-in box wasn't marked as complete. Just a gentle reminder to connect when you have a moment.
---
"""
    headers = {"Content-Type": "text/markdown"}
    response = _make_obsidian_request(
        "POST", f"vault/{file_path}", headers=headers, data=follow_up_content.encode('utf-8')
    )
    if response:
        print("Successfully appended follow-up log to today's note.")
        return True
    print("Failed to append follow-up log to Obsidian.")
    return False

# --- Test Execution ---
if __name__ == "__main__":
    # This is a placeholder for any manual testing.
    # To test state deletion, for example, you could uncomment the following:
    # from datetime import datetime
    # from src.job_commando import config
    # today = datetime.now().date()
    # print(f"--- Running State Manager Manually for Date: {today} ---")
    # delete_state(today)
    pass 