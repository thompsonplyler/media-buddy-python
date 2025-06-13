import pytest
from unittest.mock import Mock
from src.job_commando import obsidian_api
from datetime import date
import requests

def test_daily_log_exists_when_true(mocker):
    """
    Tests that the function returns True when the Obsidian API
    indicates the file exists (returns status 200).
    """
    # Arrange
    mock_response = Mock()
    mock_response.status_code = 200
    mocker.patch('requests.head', return_value=mock_response)
    
    # Act
    result = obsidian_api.daily_log_exists(date.today())
    
    # Assert
    assert result is True
    requests.head.assert_called_once()
    
def test_daily_log_exists_when_false(mocker):
    """
    Tests that the function returns False when the Obsidian API
    indicates the file does not exist (returns status 404).
    """
    # Arrange
    mock_response = Mock()
    mock_response.status_code = 404
    mocker.patch('requests.head', return_value=mock_response)
    
    # Act
    result = obsidian_api.daily_log_exists(date.today())
    
    # Assert
    assert result is False
    requests.head.assert_called_once()

def test_daily_log_exists_on_connection_error(mocker):
    """
    Tests that the function returns False when a connection error occurs.
    """
    # Arrange
    mocker.patch('requests.head', side_effect=requests.exceptions.ConnectionError)
    
    # Act
    result = obsidian_api.daily_log_exists(date.today())
    
    # Assert
    assert result is False
    requests.head.assert_called_once() 