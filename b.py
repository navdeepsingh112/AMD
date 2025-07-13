import os
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def retrive_calendar_events(user, start, end):
    events_list = []
    token_path = "./Keys/" + user.split("@")[0] + ".token"
    user_creds = Credentials.from_authorized_user_file(token_path)
    calendar_service = build("calendar", "v3", credentials=user_creds)
    
    events_result = calendar_service.events().list(
        calendarId='primary',
        timeMin=start,
        timeMax=end,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    
    for event in events:
        attendee_list = []
        try:
            for attendee in event.get("attendees", []):
                attendee_list.append(attendee.get('email', 'UNKNOWN'))
        except:
            attendee_list.append("SELF")
        
        start_time = event["start"].get("dateTime", event["start"].get("date"))
        end_time = event["end"].get("dateTime", event["end"].get("date"))

        events_list.append({
            "StartTime": start_time,
            "EndTime": end_time,
            "NumAttendees": len(set(attendee_list)),
            "Attendees": list(set(attendee_list)),
            "Summary": event.get("summary", "No Title")
        })

    return events_list

def get_event_date(event_start_time):
    """Extract date from event start time"""
    if 'T' in event_start_time:
        # DateTime format
        return event_start_time.split('T')[0]
    else:
        # Date format
        return event_start_time

def organize_events_by_date(all_events):
    """Organize events by date across all users"""
    events_by_date = {}
    
    for user, events in all_events.items():
        for event in events:
            event_date = get_event_date(event["StartTime"])
            
            if event_date not in events_by_date:
                events_by_date[event_date] = {}
            
            if user not in events_by_date[event_date]:
                events_by_date[event_date][user] = []
            
            events_by_date[event_date][user].append(event)
    
    return events_by_date

# ========================
# Main Logic
# ========================
users = ["userone.amd@gmail.com", "usertwo.amd@gmail.com", "userthree.amd@gmail.com"]

# Define date range
start = "2025-07-01T00:00:00+05:30"
end = "2025-07-10T23:59:59+05:30"

# Create output folder
os.makedirs("cal", exist_ok=True)

# Dictionary to hold all users' events
all_events = {}

for user in users:
    try:
        events = retrive_calendar_events(user, start, end)
        all_events[user] = events
        print(f"Retrieved {len(events)} events for {user}")
    except Exception as e:
        print(f"Error retrieving events for {user}: {e}")
        all_events[user] = []

# Organize events by date
events_by_date = organize_events_by_date(all_events)

# Save each date's events to separate JSON files
for date, date_events in events_by_date.items():
    output_file = f"cal/{date}.json"
    with open(output_file, "w") as f:
        json.dump(date_events, f, indent=4)
    print(f"Events for {date} saved to {output_file}")

print(f"\nTotal dates processed: {len(events_by_date)}")
print("All events have been saved to separate date-based JSON files in the 'cal' folder.")