import os
import yaml
from datetime import date
from src.media_buddy import state_manager
import unittest
from unittest.mock import patch, mock_open
from datetime import datetime, timedelta

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

class TestStateManager(unittest.TestCase):

    def setUp(self):
        # Ensure a clean state for each test
        state_manager.STATE_FILE_PATH = "instance/test_app_state.yml"
        if os.path.exists(state_manager.STATE_FILE_PATH):
            os.remove(state_manager.STATE_FILE_PATH)

    def tearDown(self):
        # Clean up the test state file
        if os.path.exists(state_manager.STATE_FILE_PATH):
            os.remove(state_manager.STATE_FILE_PATH)

    def test_get_state_no_file(self):
        """Test that get_state returns an empty dict if the file doesn't exist."""
        self.assertEqual(state_manager.get_state(), {})

    def test_save_and_get_state(self):
        """Test that state can be saved and retrieved correctly."""
        test_state = {'key': 'value', 'number': 123}
        state_manager.save_state(test_state)
        self.assertEqual(state_manager.get_state(), test_state)

    def test_update_last_checkin_time(self):
        """Test updating and retrieving a check-in time."""
        checkin_type = "test_checkin"
        
        # First, check that it's None
        self.assertIsNone(state_manager.get_last_checkin_time(checkin_type))
        
        # Now, update it
        state_manager.update_last_checkin_time(checkin_type)
        
        # Check that it's a datetime object and is recent
        checkin_time = state_manager.get_last_checkin_time(checkin_type)
        self.assertIsInstance(checkin_time, datetime)
        self.assertAlmostEqual(checkin_time, datetime.utcnow(), delta=timedelta(seconds=5)) 