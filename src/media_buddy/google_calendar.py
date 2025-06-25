import datetime
import os.path
from datetime import timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Build paths from the project root to ensure they are always correct.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "private/outside-code/google-calendar/oauth_secret.json")
TOKEN_FILE = os.path.join(PROJECT_ROOT, "private/outside-code/google-calendar/token.json")

def get_calendar_service():
    """Gets an authorized Google Calendar service instance."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
            
    return build("calendar", "v3", credentials=creds)

def create_quick_checkin_event():
    """Creates a 15-minute 'Compassionate Check-in' event on the user's primary calendar."""
    try:
        service = get_calendar_service()
        
        now = datetime.datetime.now(datetime.timezone.utc)
        start_time = now + timedelta(minutes=15)
        end_time = start_time + timedelta(minutes=15)

        event = {
            'summary': 'Compassionate Check-in',
            'description': 'A gentle nudge to check in. No judgment. Let\'s take a moment to reset. When you see this, come talk to me.',
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'America/New_York',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 5},
                ],
            },
        }

        created_event = service.events().insert(calendarId='primary', body=event).execute()
        print(f"Event created: {created_event.get('htmlLink')}")
        return True

    except Exception as error:
        print(f"An error occurred in create_quick_checkin_event: {error}")
        return False

if __name__ == '__main__':
    # This allows for testing the module directly
    create_quick_checkin_event() 