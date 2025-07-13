import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
def retrive_calendar_events(user, start, end):
    events_list = []
    token_path = "./Keys/"+user.split("@")[0]+".token"
    user_creds = Credentials.from_authorized_user_file(token_path)
    calendar_service = build("calendar", "v3", credentials=user_creds)
    events_result = calendar_service.events().list(calendarId='primary', timeMin=start,timeMax=end,singleEvents=True,orderBy='startTime').execute()
    events = events_result.get('items')
    
    for event in events : 
        attendee_list = []
        try:
            for attendee in event["attendees"]: 
                attendee_list.append(attendee['email'])
        except: 
            attendee_list.append("SELF")
        start_time = event["start"]["dateTime"]
        end_time = event["end"]["dateTime"]
        events_list.append(
            {"StartTime" : start_time, 
             "EndTime": end_time, 
             "NumAttendees" :len(set(attendee_list)), 
             "Attendees" : list(set(attendee_list)),
             "Summary" : event["summary"]})
    return events_list
def parse_meeting_request(email_content):
    """Extract meeting details from email content."""
    day = None
    duration = None
    start_time = None
    end_time = None

    # Extract day of week
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for d in days:
        if d in email_content.lower():
            day = d
            break

    # Extract duration
    duration_match = re.search(r'for (\d+) minutes', email_content.lower())
    if duration_match:
        duration = int(duration_match.group(1))

    return day, duration, start_time, end_time

def get_meeting_date(reference_date, day_name):
    """Get the next occurrence of the specified day."""
    day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
              "friday": 4, "saturday": 5, "sunday": 6}

    ref_date = datetime.datetime.strptime(reference_date, "%d-%m-%YT%H:%M:%S")
    target_day = day_map[day_name.lower()]

    days_ahead = (target_day - ref_date.weekday()) % 7
    if days_ahead == 0 and ref_date.hour >= 17:  # Same day but after business hours
        days_ahead = 7

    meeting_date = ref_date + datetime.timedelta(days=days_ahead)
    return meeting_date.strftime("%Y-%m-%d")

def get_time_bounds(meeting_date):
    """Get business hours (9AM-5PM) for the meeting date."""
    date_obj = datetime.datetime.strptime(meeting_date, "%Y-%m-%d")

    start_time = datetime.datetime(
        date_obj.year, date_obj.month, date_obj.day, 9, 0, 0
    ).isoformat() + "Z"

    end_time = datetime.datetime(
        date_obj.year, date_obj.month, date_obj.day, 17, 0, 0
    ).isoformat() + "Z"

    return start_time, end_time

def find_available_slots(users, day_start, day_end, duration):
    """Find available time slots for the meeting."""
    start_dt = datetime.datetime.fromisoformat(day_start.replace("Z", "+00:00"))
    end_dt = datetime.datetime.fromisoformat(day_end.replace("Z", "+00:00"))

    # Get events for all users
    all_events = []
    for user in users:
        events = retrive_calendar_events(user, day_start, day_end)
        all_events.extend(events)

    # Find available slots
    available_slots = []
    current_time = start_dt

    while current_time + datetime.timedelta(minutes=duration) <= end_dt:
        slot_end = current_time + datetime.timedelta(minutes=duration)
        slot_available = True

        # Check if slot conflicts with any event
        for event in all_events:
            event_start = datetime.datetime.fromisoformat(event["StartTime"].replace("Z", "+00:00"))
            event_end = datetime.datetime.fromisoformat(event["EndTime"].replace("Z", "+00:00"))

            if current_time < event_end and slot_end > event_start:
                slot_available = False
                break

        if slot_available:
            available_slots.append({
                "start": current_time.strftime("%H:%M"),
                "end": slot_end.strftime("%H:%M")
            })

        # Move to next 30-minute increment
        current_time += datetime.timedelta(minutes=30)

    return available_slots

def schedule_meeting(input_data):
    """Main function to process meeting request and find available slots."""
    # Parse email
    day, duration, _, _ = parse_meeting_request(input_data["EmailContent"])

    # Validate parsed data
    if not day:
        return {"error": "Could not determine meeting day"}
    if not duration:
        return {"error": "Could not determine meeting duration"}

    # Get meeting date and time bounds
    meeting_date = get_meeting_date(input_data["Datetime"], day)
    day_start, day_end = get_time_bounds(meeting_date)

    # Get all users
    users = [input_data["From"]] + [attendee["email"] for attendee in input_data["Attendees"]]

    # Find available slots
    available_slots = find_available_slots(users, day_start, day_end, duration)

    return {
        "meeting_day": day.capitalize(),
        "meeting_date": meeting_date,
        "duration": f"{duration} minutes",
        "available_slots": available_slots
    }

# Execute the solution
i={
    "Request_id": "6118b54f-907b-4451-8d48-dd13d76033a5",
    "Datetime": "09-07-2025T12:34:55",
    "Location": "IIT Mumbai",
    "From": "userone.amd@gmail.com",
    "Attendees": [
        {
            "email": "usertwo.amd@gmail.com"
        },
        {
            "email": "userthree.amd@gmail.com"
        }
    ],
    "Subject": "Agentic AI Project Status Update",
    "EmailContent": "Hi team, let's meet on Thursday for 30 minutes to discuss the status of Agentic AI Project."
}
result = schedule_meeting(i)
print(result)