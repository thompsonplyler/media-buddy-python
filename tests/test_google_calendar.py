import pytest
from unittest.mock import Mock, patch
from src.job_commando.google_calendar import create_quick_checkin_event
import datetime

@patch('src.job_commando.google_calendar.get_calendar_service')
def test_create_quick_checkin_event_success(mock_get_service):
    """
    Tests that the function correctly calls the Google Calendar API
    with a properly structured event.
    """
    # Arrange: Mock the entire service object and its chained calls
    mock_service = Mock()
    mock_events = Mock()
    mock_insert = Mock()
    mock_execute = Mock()

    # Configure the mock objects to simulate the chain: service.events().insert().execute()
    mock_get_service.return_value = mock_service
    mock_service.events.return_value = mock_events
    mock_events.insert.return_value = mock_insert
    mock_insert.execute.return_value = {'htmlLink': 'http://test.link'}

    # Act: Call the function we are testing
    result = create_quick_checkin_event()

    # Assert: Verify the outcome and the details of the call
    assert result is True
    mock_get_service.assert_called_once()
    mock_service.events.assert_called_once()
    
    # Check that insert was called, and inspect what it was called with
    mock_events.insert.assert_called_once()
    call_args = mock_events.insert.call_args
    assert call_args.kwargs['calendarId'] == 'primary'
    
    event_body = call_args.kwargs['body']
    assert event_body['summary'] == 'Compassionate Check-in'
    assert 'A gentle nudge' in event_body['description']
    assert 'dateTime' in event_body['start']
    assert 'dateTime' in event_body['end']

@patch('src.job_commando.google_calendar.get_calendar_service')
def test_create_quick_checkin_event_failure(mock_get_service):
    """
    Tests that the function returns False when the API call fails.
    """
    # Arrange: Mock the service to raise an exception
    mock_get_service.side_effect = Exception("API connection failed")

    # Act: Call the function
    result = create_quick_checkin_event()

    # Assert: Verify it returns our failure code
    assert result is False 