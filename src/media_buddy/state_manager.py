import json
import requests
from datetime import datetime
import yaml
import os

from . import config

def get_default_state():
    """Returns the default state for a new day."""
    return {
        "league_vortex_triggered": False,
        "radio_silence_triggered": False,
        "follow_up_triggered": False
    }

def get_state_file_path(date: datetime.date) -> str:
    """Constructs the vault-internal path for a given date's state file."""
    return f"{config.STATE_PATH_PREFIX}/state_{date.strftime(config.DATE_FORMAT)}.json"

def load_state(date: datetime.date) -> dict:
    """
    Loads state from a file in the vault via the API.
    If the file doesn't exist (404), returns the default state.
    """
    vault_path = get_state_file_path(date)
    url = f"{config.OBSIDIAN_API_BASE_URL}/vault/{vault_path}"
    headers = {"Authorization": f"Bearer {config.OBSIDIAN_API_KEY}"}

    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 404:
            print(f"No state file found for today at '{vault_path}'. Creating default state.")
            return get_default_state()
        
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error loading state from Obsidian API: {e}")
        return get_default_state()
    except json.JSONDecodeError:
        print(f"Could not decode JSON from state file at '{vault_path}'. Using default state.")
        return get_default_state()

def save_state(date: datetime.date, state: dict):
    """Saves the state to a file in the vault via a PUT request."""
    vault_path = get_state_file_path(date)
    url = f"{config.OBSIDIAN_API_BASE_URL}/vault/{vault_path}"
    headers = {
        "Authorization": f"Bearer {config.OBSIDIAN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        # Using a PUT request to create or completely overwrite the file.
        response = requests.put(url, headers=headers, data=json.dumps(state, indent=4), verify=False)
        response.raise_for_status()
        print(f"Successfully saved state to '{vault_path}' in Obsidian vault.")
    except requests.exceptions.RequestException as e:
        print(f"Error saving state to Obsidian API: {e}")

def delete_state(date: datetime.date):
    """Deletes the state file for a given date from the vault via the API."""
    vault_path = get_state_file_path(date)
    url = f"{config.OBSIDIAN_API_BASE_URL}/vault/{vault_path}"
    headers = {"Authorization": f"Bearer {config.OBSIDIAN_API_KEY}"}

    print(f"Attempting to delete state file at '{vault_path}'...")
    try:
        response = requests.delete(url, headers=headers, verify=False)
        if response.status_code == 404:
            print("State file not found. Nothing to delete.")
            return

        response.raise_for_status()
        print(f"Successfully deleted state file from vault.")
    except requests.exceptions.RequestException as e:
        print(f"Error deleting state file from Obsidian API: {e}")

# --- Test Execution ---
if __name__ == "__main__":
    # This block allows for manual state deletion for testing purposes.
    from src.media_buddy import config # Re-import for test scope
    today = datetime.now().date()
    print(f"--- Running State Manager Manually for Date: {today} ---")
    delete_state(today)

# This is a simple file-based state manager.
# In a larger application, this might be Redis, a database, etc.
STATE_FILE_PATH = "instance/app_state.yml"

def get_state():
    """Returns the current application state."""
    return {}

def save_state(new_state):
    """Saves the application state to the YAML file."""
    try:
        # Ensure the instance directory exists
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        with open(STATE_FILE_PATH, 'w') as f:
            yaml.safe_dump(new_state, f)
    except Exception as e:
        print(f"Error saving state: {e}")

def get_last_checkin_time(checkin_type):
    """Returns the last check-in time for a given check-in type."""
    state = get_state()
    return state.get(checkin_type)

def update_last_checkin_time(checkin_type):
    """Updates the timestamp for a given check-in type to now."""
    state = get_state()
    state[checkin_type] = datetime.utcnow()
    save_state(state)

# --- Test Cases ---
if __name__ == '__main__':
    # This block allows for direct testing of the state manager.
    
    # To run this test, you need to ensure the application's config is loaded
    # because this script might be run from a different context than the main app.
    # This is a common pattern for making modules runnable and testable.
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from src.media_buddy import config # Re-import for test scope

    def test_state_manager():
        print("--- Testing State Manager ---")
        
        # 1. Clean up old state file if it exists
        # ... existing code ...

        # ... rest of the test code ... 