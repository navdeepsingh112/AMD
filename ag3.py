#sushant part
from datetime import datetime, timedelta
import requests
import json

# --- Test input ---
input_data = {
    "Request_id": "6118b54f-907b-4451-8d48-dd13d76033a5",
    "Datetime": "09-07-2025T12:34:55",
    "Location": "IIT Mumbai",
    "From": "userone.amd@gmail.com",
    "Attendees": [
        {"email": "usertwo.amd@gmail.com"},
        {"email": "userthree.amd@gmail.com"}
    ],
    "Subject": "Agentic AI Project Status Update",
    "EmailContent": "Hi team, let's have a meet on thursday for 30 minutes to discuss the status of Agentic AI Project."
}

# --- Send prompt to local LLM endpoint ---
def llm(msg):
    url = "http://134.199.195.53:5000/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": "/home/user/Models/meta-llama/Llama-3.3-70B-Instruct",
        "messages": [
            {"role": "system", "content": "You are an expert. Return only a JSON object."},
            {"role": "user", "content": msg}
        ],
        "stream": False,
        "max_tokens": 128
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

# --- Compute next specific weekday from a given date ---
def get_next_weekday(from_date, target_weekday_str):
    """
    Given a starting date and a target weekday name, return the date of the next target weekday.
    E.g., if from_date is Wednesday and target_weekday is Thursday, return the next day.
    """
    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6
    }

    target_weekday = weekday_map.get(target_weekday_str.lower())
    if target_weekday is None:
        return from_date  # fallback to same day if unknown

    days_ahead = (target_weekday - from_date.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7  # next occurrence, not today
    return from_date + timedelta(days=days_ahead)

# --- Build context using only email received date ---
def build_context(input_datetime_str, email_content):
    """
    Generates a clean context with resolved weekday.
    For example: email sent on Wednesday and mentions 'Thursday' → calculates that Thursday's date.
    """
    email_dt = datetime.strptime(input_datetime_str, "%d-%m-%YT%H:%M:%S")
    email_day = email_dt.strftime("%A")
    email_date = email_dt.strftime("%d-%m-%Y")
    email_time = email_dt.strftime("%H:%M:%S")

    # Try to extract the next meeting day mentioned in content
    weekday_keywords = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    mentioned_day = None
    for word in email_content.lower().split():
        if word.strip(",.") in weekday_keywords:
            mentioned_day = word.strip(",.")
            break

    # If day is mentioned, compute its next occurrence
    next_meeting_date = get_next_weekday(email_dt, mentioned_day) if mentioned_day else email_dt

    # Build reference-based instruction
    context = (
        f"The email was received on {email_day}, {email_date} at {email_time}. "
        f"It mentions meeting on '{mentioned_day.capitalize()}' if any. "
        f"The next '{mentioned_day.capitalize()}' after the email date is {next_meeting_date.strftime('%Y-%m-%d')}."
    )
    return context, next_meeting_date

def process_input(input_data):
    """
    Extracts structured meeting info from natural language content using internal weekday mapping.
    Now supports fallback to full-day window if time is not mentioned.
    """
    context, resolved_meeting_date = build_context(input_data['Datetime'], input_data['EmailContent'])

    prompt = f"""
    Extract meeting details from this email content:

    Email Content: "{input_data['EmailContent']}"
    Subject: "{input_data['Subject']}"

    Use this reference context for scheduling:
    {context}

    Return JSON with:
    - starttime: Use resolved meeting date at 00:00:00 in ISO format if time not mentioned
    - endtime: 30 minutes after starttime if time is mentioned; otherwise use 23:59:59 of same day
    - duration: in minutes
    - priority: true if words like "urgent", "asap", or "important" are used
    - Return in GMT format (YYYY-MM-DDTHH:MM:SS+00:00)

    Format:
    {{
      "starttime": "...",
      "endtime": "...",
      "duration": ...,
      "priority": ...
    }}
    """

    # Query the LLM
    llm_response = llm(prompt)

    # Extract & clean
    raw = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
    print("LLM Raw Output:\n", raw)

    try:
        cleaned = raw.strip().strip("json").strip("")
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        data = {}

    # Determine final start & end time
    default_start = resolved_meeting_date.strftime('%Y-%m-%dT00:00:00')
    default_end = resolved_meeting_date.strftime('%Y-%m-%dT23:59:59')

    starttime = data.get("starttime", default_start)
    endtime = data.get("endtime", default_end)

    # If LLM gave starttime but it's exactly T00:00:00, and endtime is T00:30:00 → likely no time mentioned.
    # So force fallback to full day window
    if starttime.endswith("T00:00:00") and (endtime.endswith("T00:30:00") or endtime == starttime):
        endtime = default_end

    final_data = input_data.copy()
    final_data["starttime"] = starttime
    final_data["endtime"] = endtime
    final_data["duration"] = data.get("duration", 30)
    final_data["priority"] = data.get("priority", False)

    return final_data
def find_common_free_slots(processed_input):
    """
    Find common free slots between sender and attendees within the specified time range.

    Args:
        processed_input: Dictionary containing meeting details with starttime, endtime, duration, From, and Attendees

    Returns:
        List of dictionaries containing free slot information with start and end times
    """

    # Extract required information
    start_time = processed_input['starttime']
    end_time = processed_input['endtime']
    duration = processed_input['duration']
    sender = processed_input['From']
    attendees = processed_input['Attendees']

    # Function to ensure datetime string has GMT format
    # def ensure_gmt_format(dt_string):
    #     """Ensure datetime string is in ISO 8601 format with timezone"""
    #     if dt_string.endswith('Z'):
    #         return dt_string.replace('Z', '+00:00')
    #     elif dt_string[-5] == '+':
    #         return dt_string
    #     else:
    #         try:
    #             dt_obj = datetime.fromisoformat(dt_string)
    #             return dt_obj.isoformat() + '+00:00'
    #         except:
    #             return dt_string + '+00:00'

    # # Ensure start and end time are in proper format
    # start_time = ensure_gmt_format(start_time)
    # end_time = ensure_gmt_format(end_time)

    # Create list of all participants
    all_participants = [sender] + [attendee['email'] for attendee in attendees]

    # Get all calendar events
    all_events = []
    for participant in all_participants:
        try:
            participant_events = retrive_calendar_events(participant, start_time, end_time)
            for event in participant_events:
                all_events.append({
                    'start': event['StartTime'],
                    'end': event['EndTime'],
                    'participant': participant
                })
        except Exception as e:
            print(f"Error retrieving events for {participant}: {e}")
            continue

    # Convert string times to datetime objects

    # Sort events by start time
    all_events.sort(key=lambda x: x['start_dt'])

    # Convert meeting range to datetime
    start_dt = datetime.fromisoformat(start_time)
    end_dt = datetime.fromisoformat(end_time)

    # Merge overlapping events
    merged_events = []
    for event in all_events:
        if not merged_events:
            merged_events.append(event)
        else:
            last_event = merged_events[-1]
            if event['start_dt'] <= last_event['end_dt']:
                last_event['end_dt'] = max(last_event['end_dt'], event['end_dt'])
            else:
                merged_events.append(event)

    # Find free slots
    free_slots = []
    current_time = start_dt

    for event in merged_events:
        if current_time < event['start_dt']:
            gap_duration = (event['start_dt'] - current_time).total_seconds() / 60
            if gap_duration >= duration:
                free_slots.append({
                    'start': current_time.isoformat(),
                    'end': event['start_dt'].isoformat(),
                    'duration_minutes': int(gap_duration)
                })
        current_time = max(current_time, event['end_dt'])

    # Check for free time after the last event
    if current_time < end_dt:
        gap_duration = (end_dt - current_time).total_seconds() / 60
        if gap_duration >= duration:
            free_slots.append({
                'start': current_time.isoformat(),
                'end': end_dt.isoformat(),
                'duration_minutes': int(gap_duration)
            })

    # If no events at all, full range is free
    if not merged_events:
        total_duration = (end_dt - start_dt).total_seconds() / 60
        if total_duration >= duration:
            free_slots.append({
                'start': start_dt.isoformat(),
                'end': end_dt.isoformat(),
                'duration_minutes': int(total_duration)
            })

    return free_slots
p = process_input(input_data)
free_slots = find_common_free_slots(p)
print("Processed Input:", p)
print("Free Slots:", free_slots)