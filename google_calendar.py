from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle
from datetime import datetime, timedelta

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_google_calendar_service():
    """Shows basic usage of the Google Calendar API.
    Returns the authorized Google Calendar API service.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)
    return service

def create_calendar_event(service, schedule):
    """Creates a Google Calendar event for a given schedule."""
    try:
        # Convert schedule time to datetime objects
        start_time = datetime.strptime(schedule['start_time'], '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(schedule['end_time'], '%Y-%m-%d %H:%M:%S')
        
        # Ensure proper timezone formatting for Google Calendar API
        event = {
            'summary': schedule['caregiver_name'],  # Just use the caregiver's name
            'description': f"Client: {schedule['client_name']}\nNotes: {schedule.get('notes', '')}",
            'start': {
                'dateTime': start_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': schedule.get('timezone', 'America/Los_Angeles'),
            },
            'end': {
                'dateTime': end_time.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': schedule.get('timezone', 'America/Los_Angeles'),
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 120},  # 2 hour reminder
                ],
            },
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        return event.get('htmlLink')
    except Exception as e:
        print(f"Error creating calendar event: {str(e)}")
        return None

def export_schedule_to_calendar(schedule):
    """Exports a schedule to Google Calendar."""
    try:
        service = get_google_calendar_service()
        event_link = create_calendar_event(service, schedule)
        return event_link
    except Exception as e:
        print(f"Error exporting to calendar: {str(e)}")
        return None 