from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import requests
from datetime import datetime, timedelta
import json
import re
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz
from typing import List, Dict, Union, Any


def get_gmt_offset(location_name: str) -> str:
    """
    Returns the GMT offset of a location in +HH:MM format.

    Args:
        location_name (str): City or location name

    Returns:
        str: GMT offset string, e.g., '+05:30', '-04:00'
    """
    try:
        # Step 1: Geocode location
        geolocator = Nominatim(user_agent="gmt_offset_finder")
        location = geolocator.geocode(location_name)
        if not location:
            return f"Error: Location '{location_name}' not found."

        lat, lon = location.latitude, location.longitude

        # Step 2: Get timezone name from lat/lon
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lng=lon, lat=lat)
        if not tz_name:
            return f"Error: Timezone not found for location."

        # Step 3: Localize current UTC time and get offset
        tz = pytz.timezone(tz_name)
        now_utc = datetime.utcnow()
        localized_time = pytz.utc.localize(now_utc).astimezone(tz)
        offset = localized_time.utcoffset()

        if offset is None:
            return f"Error: Unable to calculate offset."

        total_minutes = int(offset.total_seconds() / 60)
        hours = total_minutes // 60
        minutes = abs(total_minutes % 60)
        sign = '+' if total_minutes >= 0 else '-'
        return f"{sign}{abs(hours):02}:{minutes:02}"

    except Exception as e:
        return f"Error: {str(e)}"
input_data = {
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
def retrive_calendar_events(user, start, end):
    events_list = []
    print(user, start, end)
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
def llm(msg):
    url = "http://134.199.195.53:5000/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "/home/user/Models/meta-llama/Llama-3.3-70B-Instruct",
        "messages": [
            {
                "role": "system",
                "content": "You are an expert give only the required response in JSON format"
            },
            {
                "role": "user",
                "content": msg
            }
        ],
        "stream": False,
        "max_tokens": 128
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()
def process_input(input_data):
    """
    Process the input data and extract meeting details using LLM
    Returns the input data with additional fields: starttime, endtime, duration, priority
    """
    
    # Get timezone from location
    # location = input_data.get('Location', '')
    # timezone_str = get_timezone_from_location(location)
    
    # Create prompt for LLM to extract meeting details
    prompt = f"""
    Extract meeting details from the following email content and datetime:
    
    Datetime the email was sent on: {input_data['Datetime']} in DD:MM:YYYYTHH:MM:SS format 
    Email Content: {input_data['EmailContent']}
    Subject: {input_data['Subject']}
    
    Please extract and return ONLY a JSON object with these fields:
    - starttime: in GMT format of when the meeting can start.YYYY:MM:DDT00:00:00. if a specific time is mentioned then taht time.
    - endtime: in GMT format of when the meeting can end.  YYYY:MM:DDT23:59:59.if a specific time is mentioned then taht time.
    - day : if day like "Thursday" is mentioned then return that day else return null.
    - duration: meeting duration in minutes
    - priority: boolean indicating if this is high priority
    NOTE: 
    - GMT format = format (YYYY-MM-DDTHH:MM:SS)
    - USE EMAIL content to determinr starttime , endtime, and duration.
    - 09-07-2025 (DD:MM:YYYY) was Wednesday 
    - calculate starttime and endtime if a day like "Thursday" is mentioned using the refernce )9-07-2025 which is Wednesday.
    Consider the email content mentions meeting day and duration. Use the datetime as reference for scheduling.
    """
    llm_response = llm(prompt)
    # llm_response = json.loads(llm_response.strip('```json\n').strip('```'))
    # Extract the content from LLM response
    extracted_info = llm_response.get('choices', [{}])[0].get('message', {}).get('content', '{}')
    print("LLM Response:", extracted_info)
    # Parse the JSON response
    meeting_details = json.loads(extracted_info.strip('```json\n').strip('```'))

    
    # Create processed input by copying original data
    processed_input = input_data.copy()
    
    # Add the extracted fields
    processed_input['starttime'] = meeting_details.get('starttime', '2025-07-10T09:00:00Z')
    processed_input['endtime'] = meeting_details.get('endtime', '2025-07-10T17:00:00Z')
    processed_input['duration'] = meeting_details.get('duration', 30)
    processed_input['priority'] = meeting_details.get('priority', False)
    G = get_gmt_offset(input_data['Location'])
    processed_input['starttime'] = processed_input['starttime']  + G
    processed_input['endtime'] = processed_input['endtime'] + G
    return processed_input
from datetime import datetime, timedelta

def find_common_free_slots(processed_input):
    """
    Finds and chunks common free slots, correctly handling events that
    span across the boundaries of the search window (e.g., overnight events).

    Args:
        processed_input (dict): A dictionary containing the meeting details.

    Returns:
        list: A list of bookable slots of the specified duration.
    """
    # --- Step 0: Extract Inputs and Define Search Window ---
    start_time_str = processed_input['starttime']
    end_time_str = processed_input['endtime']
    duration_minutes = processed_input['duration']
    sender = processed_input['From']
    attendees = processed_input.get('Attendees', [])

    search_start_dt = datetime.fromisoformat(start_time_str)
    search_end_dt = datetime.fromisoformat(end_time_str)
    all_participant_emails = [sender] + [attendee['email'] for attendee in attendees]

    all_busy_times = []

    # --- Step 1: Fetch, Clip, and Merge Events for Each Participant ---
    for participant in all_participant_emails:
        try:
            # Assume retrive_calendar_events exists and works as before
            participant_events = [] # Replace with actual call
        except Exception as e:
            print(f"Could not retrieve events for {participant}: {e}")
            return []

        # **THE CORRECTION: Clip events to the search window before merging**
        clipped_events = []
        for event in participant_events:
            event_start_dt = datetime.fromisoformat(event['StartTime'])
            event_end_dt = datetime.fromisoformat(event['EndTime'])

            # Find the actual overlap between the event and the search window
            effective_start = max(event_start_dt, search_start_dt)
            effective_end = min(event_end_dt, search_end_dt)

            # Only consider the event if it's actually within our search window
            if effective_start < effective_end:
                clipped_events.append({
                    'start_dt': effective_start,
                    'end_dt': effective_end
                })

        if not clipped_events:
            continue

        # Now, sort and merge the *clipped* events for the participant
        clipped_events.sort(key=lambda x: x['start_dt'])

        merged_participant_events = []
        for event in clipped_events:
            if not merged_participant_events:
                merged_participant_events.append(event)
            else:
                last_event = merged_participant_events[-1]
                if event['start_dt'] <= last_event['end_dt']:
                    last_event['end_dt'] = max(last_event['end_dt'], event['end_dt'])
                else:
                    merged_participant_events.append(event)

        all_busy_times.extend(merged_participant_events)

    # --- Steps 2, 3 & 4: Merge all busy times, find gaps, and chunk slots ---
    # (The rest of the logic remains the same as the previous version)
    
    if not all_busy_times:
        # The entire range is potentially free
        if (search_end_dt - search_start_dt) >= timedelta(minutes=duration_minutes):
             # This part needs the chunking logic as well
             pass # Add chunking logic here for a completely free day
        else:
            return []

    all_busy_times.sort(key=lambda x: x['start_dt'])

    merged_busy_timeline = []
    # ... [rest of the merging, gap-finding, and chunking logic] ...
            
    # For clarity, the final logic is reproduced here
    # Merge all busy periods into a single timeline
    if all_busy_times:
      merged_busy_timeline.append(all_busy_times[0])
      for busy_period in all_busy_times[1:]:
          last_busy = merged_busy_timeline[-1]
          if busy_period['start_dt'] <= last_busy['end_dt']:
              last_busy['end_dt'] = max(last_busy['end_dt'], busy_period['end_dt'])
          else:
              merged_busy_timeline.append(busy_period)

    # Find gaps (large free slots) between the busy times
    large_free_slots = []
    current_time = search_start_dt
    for busy_period in merged_busy_timeline:
        if current_time < busy_period['start_dt']:
            large_free_slots.append({'start': current_time, 'end': busy_period['start_dt']})
        current_time = max(current_time, busy_period['end_dt'])
    
    # Check for a final free slot at the end of the day
    if current_time < search_end_dt:
        large_free_slots.append({'start': current_time, 'end': search_end_dt})

    # Chunk the large slots into the required duration
    final_chunked_slots = []
    required_duration = timedelta(minutes=duration_minutes)
    for slot in large_free_slots:
        chunk_start_time = slot['start']
        while chunk_start_time + required_duration <= slot['end']:
            chunk_end_time = chunk_start_time + required_duration
            final_chunked_slots.append({
                'start': chunk_start_time.isoformat(),
                'end': chunk_end_time.isoformat()
            })
            chunk_start_time = chunk_end_time
            
    return final_chunked_slots


p = process_input(input_data)
free_slots = find_common_free_slots(p)
print("Processed Input:", p)
print("Free Slots:", free_slots)

def parse_dd_mm_yyyy(datetime_str: str) -> datetime:
    return datetime.strptime(datetime_str, "%d-%m-%YT%H:%M:%S")

email = {
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
    "EmailContent": "Hi team, let's meet on Thursday for 30 minutes to discuss the status of Agentic AI Project.",
    "Start": "2025-07-17T00:00:00+05:30",
    "End": "2025-07-17T23:59:59+05:30",
    "Duration_mins": "30"
}

required_duration = int(email["Duration_mins"])
final = []

def build_enriched_event(email: Dict[str, Any], final: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Parse the email "sent" time
    sent_time = parse_dd_mm_yyyy(email["Datetime"])

    
    # Time window: same day from 00:00 to 23:59:59 IST
    day_start = sent_time.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + "+05:30"
    day_end = sent_time.replace(hour=23, minute=59, second=59, microsecond=0).isoformat() + "+05:30"

    # Gather unique participants (including sender)
    all_participants = list(set(
        [email["From"]] + [a["email"] for a in email["Attendees"]]
    ))

    # Initialize enriched email dict
    enriched_email = {k: email[k] for k in [
        "Request_id", "Datetime", "Location", "From", "Attendees", "Subject", "EmailContent"
    ]}

    # Collect events for each participant
    enriched_attendees = []
    for user in all_participants:
        user_events = retrive_calendar_events(user, day_start, day_end)
        enriched_attendees.append({
            "email": user,
            "events": user_events
        })

    enriched_email["Attendees"] = enriched_attendees

    # Look for event matching the subject (case-insensitive)
    subject = email["Subject"].lower()
    matched_event = None
    for attendee in enriched_attendees:
        for event in attendee["events"]:
            if subject in event["Summary"].lower():
                matched_event = event
                break
        if matched_event:
            break

    if matched_event:
        enriched_email["EventStart"] = matched_event["StartTime"]
        enriched_email["EventEnd"] = matched_event["EndTime"]
        enriched_email["Duration_mins"] = str(
            int((datetime.fromisoformat(matched_event["EndTime"]) - datetime.fromisoformat(matched_event["StartTime"])).total_seconds() // 60)
        )
    else:
        enriched_email["EventStart"] = None
        enriched_email["EventEnd"] = None
        enriched_email["Duration_mins"] = None
    chosen_slot = final[0]  # You can randomize if needed

    enriched_email["EventStart"] = chosen_slot["start"]
    enriched_email["EventEnd"] = chosen_slot["end"]
    enriched_email["Duration_mins"] = str(email["duration"])
    enriched_email["MetaData"] = {}
    # Build the current event
    current_event = {
        "StartTime": enriched_email["EventStart"],
        "EndTime": enriched_email["EventEnd"],
        "NumAttendees": len(enriched_email["Attendees"]),
        "Attendees": [att["email"] for att in enriched_email["Attendees"]],
        "Summary": enriched_email["Subject"]
    }

    # Append to each attendee's event list
    for attendee in enriched_email["Attendees"]:
        if "events" not in attendee:
            attendee["events"] = []
        attendee["events"].append(current_event)

    return enriched_email


result = build_enriched_event(p, free_slots)
print(json.dumps(result, indent=2))