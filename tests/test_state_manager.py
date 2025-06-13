import os
import yaml
from datetime import date
from src.job_commando import state_manager

def test_load_and_save_state(tmpdir):
    """
    Tests that the state can be saved to a file and loaded back correctly.
    It uses a temporary directory provided by pytest's tmpdir fixture.
    """
    # Arrange: Override the STATE_DIR constant to use our temporary directory
    state_manager.STATE_DIR = str(tmpdir)
    
    today = date.today()
    test_state = {
        "league_vortex_triggered": True,
        "radio_silence_triggered": False
    }

    # Act: Save the state
    state_manager.save_state(today, test_state)
    
    # Assert: Check that the file was created
    expected_file_path = os.path.join(str(tmpdir), f"{today.strftime(state_manager.DATE_FORMAT)}.md")
    assert os.path.exists(expected_file_path)

    # Act: Load the state back
    loaded_state = state_manager.load_state(today)

    # Assert: Check that the loaded state matches the saved state
    assert loaded_state == test_state

def test_load_default_state_when_file_nonexistent(tmpdir):
    """
    Tests that a default state is returned when the state file for the date
    does not exist.
    """
    # Arrange: Override the STATE_DIR constant
    state_manager.STATE_DIR = str(tmpdir)
    today = date.today()

    # Act: Attempt to load state from a directory where the file doesn't exist
    loaded_state = state_manager.load_state(today)

    # Assert: Verify it returns the default state
    assert loaded_state == state_manager.get_default_state()
    assert loaded_state["league_vortex_triggered"] is False 