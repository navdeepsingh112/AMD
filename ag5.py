from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import requests
from datetime import datetime, timedelta
import json
import re
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import pytz



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
def retrive_calendar_events(user, start, end):
    events_list = []
    # print(user, start, end)
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
    url = "http://localhost:3000/v1/chat/completions"
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
    Extract meeting details from the following email content and datetime.

    Datetime the email was sent on: {input_data['Datetime']} (in DD-MM-YYYYTHH:MM:SS format)
    Email Content: "{input_data['EmailContent']}"
    Subject: "{input_data['Subject']}"

    You MUST return only a valid JSON object with the following fields:
    - "starttime": the start date and time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS). 
    • If a day like "Thursday" is mentioned, compute the next such day based on the email date (09-07-2025 is Wednesday).
    • If no specific time is mentioned, set the time to T00:00:00 (start of the day).

    - "endtime": the meeting end time in ISO format.
    • If a specific time is given in the email, set this to 30 minutes after the mentioned start time.
    • If NO time is mentioned, set it to T23:59:59 (end of the day).

    - "day": the day mentioned in the email, e.g., "Thursday", or null if no day is mentioned.

    - "duration": meeting duration in minutes, based on the email content (e.g., "30 minutes").

    - "priority": true if the email contains urgency markers such as "urgent", "asap", "immediately", "important", etc. Otherwise, false.

    Examples:
    → If email says "let’s meet on Thursday" with no time:  
    Return "starttime": "2025-07-10T00:00:00" and "endtime": "2025-07-10T23:59:59"

    → If it says "let’s meet on Thursday at 10am for 30 minutes":  
    Return "starttime": "2025-07-10T10:00:00" and "endtime": "2025-07-10T10:30:00"

    Return only the JSON object. No extra text or explanation.
    """
    llm_response = llm(prompt)
    # llm_response = json.loads(llm_response.strip('```json\n').strip('```'))
    # Extract the content from LLM response
    extracted_info = llm_response.get('choices', [{}])[0].get('message', {}).get('content', '{}')
    # print("LLM Response:", extracted_info)
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
def find_common_free_slots(processed_input):
    """
    Finds common free time slots for all participants, ensuring everyone is available.

    This function identifies time slots of a minimum specified duration within a given
    time range where the sender and all attendees are simultaneously free. It works by:
    1.  Retrieving busy calendar events for every participant.
    2.  Merging the overlapping or adjacent busy intervals for each person individually.
    3.  Combining all participants' busy schedules into a single timeline of "busy" periods.
    4.  Identifying the gaps between these busy periods as potential free slots.
    5.  Filtering these slots to ensure they meet the required meeting duration.

    Args:
        processed_input (dict): A dictionary containing the meeting details:
            - 'starttime' (str): The start of the time range to search (ISO format).
            - 'endtime' (str): The end of the time range to search (ISO format).
            - 'duration' (int): The required duration of the meeting in minutes.
            - 'From' (str): The email address of the meeting organizer.
            - 'Attendees' (list): A list of dictionaries, each with an 'email' key.

    Returns:
        list: A list of dictionaries, where each dictionary represents a common
              free slot with 'start' and 'end' keys in ISO format.
    """
    # Extract required information from the input dictionary
    start_time_str = processed_input['starttime']
    end_time_str = processed_input['endtime']
    duration_minutes = processed_input['duration']
    sender = processed_input['From']
    attendees = processed_input.get('Attendees', [])
    
    all_participant_emails = [sender] + [attendee['email'] for attendee in attendees]

    # --- Step 1: Fetch and Merge Busy Times for Each Participant ---
    all_busy_times = []
    
    # Assume retrive_calendar_events exists and fetches events for a user
    # This part remains the same as your original function
    for participant in all_participant_emails:
        try:
            # This is a placeholder for your actual event retrieval function
            # retrive_calendar_events(participant, start_time, end_time)
            participant_events = [] # Replace with actual call
        except Exception as e:
            print(f"Could not retrieve events for {participant}: {e}")
            # If we can't get someone's calendar, we cannot find a common slot.
            # Depending on requirements, you might want to proceed or stop.
            # For this implementation, we will stop.
            return []

        if not participant_events:
            continue
        
        # Convert event times to datetime objects
        for event in participant_events:
            event['start_dt'] = datetime.fromisoformat(event['StartTime'])
            event['end_dt'] = datetime.fromisoformat(event['EndTime'])
            
        # Sort events by start time to merge them correctly
        participant_events.sort(key=lambda x: x['start_dt'])
        
        # Merge overlapping/adjacent events for the current participant
        merged_participant_events = []
        for event in participant_events:
            if not merged_participant_events:
                merged_participant_events.append(event)
            else:
                last_event = merged_participant_events[-1]
                if event['start_dt'] <= last_event['end_dt']:
                    # Overlap detected, merge the events by extending the end time
                    last_event['end_dt'] = max(last_event['end_dt'], event['end_dt'])
                else:
                    merged_participant_events.append(event)
        
        # Add the consolidated busy times to the main list
        all_busy_times.extend(merged_participant_events)

    # --- Step 2: Merge All Busy Times into a Single Timeline ---
    if not all_busy_times:
        # If no one has any events, the entire range is free if it's long enough
        start_dt = datetime.fromisoformat(start_time_str)
        end_dt = datetime.fromisoformat(end_time_str)
        if (end_dt - start_dt) >= timedelta(minutes=duration_minutes):
            return [{'start': start_time_str, 'end': end_time_str}]
        else:
            return []

    # Sort all busy periods from all participants by their start time
    all_busy_times.sort(key=lambda x: x['start_dt'])
    
    # Now merge these consolidated busy periods
    merged_busy_timeline = []
    for busy_period in all_busy_times:
        if not merged_busy_timeline:
            merged_busy_timeline.append(busy_period)
        else:
            last_busy = merged_busy_timeline[-1]
            if busy_period['start_dt'] <= last_busy['end_dt']:
                last_busy['end_dt'] = max(last_busy['end_dt'], busy_period['end_dt'])
            else:
                merged_busy_timeline.append(busy_period)

    # --- Step 3: Find Gaps Between Busy Times (Common Free Slots) ---
    free_slots = []
    search_start_dt = datetime.fromisoformat(start_time_str)
    search_end_dt = datetime.fromisoformat(end_time_str)
    
    # Check for free time before the first busy slot
    first_busy_start = merged_busy_timeline[0]['start_dt']
    if search_start_dt < first_busy_start:
        free_slots.append({'start': search_start_dt, 'end': first_busy_start})

    # Check for free time between the busy slots
    for i in range(len(merged_busy_timeline) - 1):
        end_of_current_busy = merged_busy_timeline[i]['end_dt']
        start_of_next_busy = merged_busy_timeline[i+1]['start_dt']
        if end_of_current_busy < start_of_next_busy:
            free_slots.append({'start': end_of_current_busy, 'end': start_of_next_busy})

    # Check for free time after the last busy slot
    last_busy_end = merged_busy_timeline[-1]['end_dt']
    if last_busy_end < search_end_dt:
        free_slots.append({'start': last_busy_end, 'end': search_end_dt})
        
    # --- Step 4: Filter Slots by Required Duration ---
    final_available_slots = []
    required_duration = timedelta(minutes=duration_minutes)
    
    for slot in free_slots:
        if slot['end'] - slot['start'] >= required_duration:
            final_available_slots.append({
                'start': slot['start'].isoformat(),
                'end': slot['end'].isoformat()
            })
    final=[]
    for slot in final_available_slots:
        current_time = slot['start']
        # Loop from the start of the large slot, creating chunks
        # print(current_time + required_duration, slot['end'])
        while current_time + required_duration <= slot['end']:
            slot_end_time = current_time + required_duration
            final.append({
                'start': current_time.isoformat(),
                'end': slot_end_time.isoformat()
            })
            # Move to the end of the newly created chunk to start the next one
            current_time = slot_end_time
    return final
def parse_dd_mm_yyyy(datetime_str: str) -> datetime:
    return datetime.strptime(datetime_str, "%d-%m-%YT%H:%M:%S")
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
