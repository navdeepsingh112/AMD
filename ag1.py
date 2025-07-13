import json
import re
import datetime
from datetime import timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build




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
class MeetingSchedulerAgent:
    def __init__(self):
        """Initialize the meeting scheduler agent"""
        pass

    def process_email_input(self, input_data):
        """Process the input email to extract meeting details"""
        processed_input = input_data.copy()

        # Extract day of the week from email content
        email_content = input_data["EmailContent"]
        day_match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', email_content, re.IGNORECASE)
        meeting_day = day_match.group(1) if day_match else None

        # Extract duration from email content
        duration_match = re.search(r'(\d+)\s*(minutes|mins|min|hour|hours|hrs)', email_content, re.IGNORECASE)
        duration_value = int(duration_match.group(1)) if duration_match else 30  # Default to 30 minutes
        duration_unit = duration_match.group(2).lower() if duration_match else "minutes"

        if "hour" in duration_unit:
            duration_minutes = duration_value * 60
        else:
            duration_minutes = duration_value

        # Calculate the date of the next occurrence of the specified day
        current_date = datetime.datetime.strptime(input_data["Datetime"], "%d-%m-%YT%H:%M:%S")
        days_of_week = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}

        if meeting_day:
            target_day = days_of_week[meeting_day.lower()]
            current_day = current_date.weekday()
            days_until_meeting = (target_day - current_day) % 7
            if days_until_meeting == 0 and current_date.hour >= 17:  # If it's the same day but after 5 PM
                days_until_meeting = 7  # Schedule for next week
            meeting_date = current_date + timedelta(days=days_until_meeting)
        else:
            # Default to next day if no day specified
            meeting_date = current_date + timedelta(days=1)

        # Set start and end times for the day
        start_time = datetime.datetime(meeting_date.year, meeting_date.month, meeting_date.day, 0, 0, 0)
        end_time = datetime.datetime(meeting_date.year, meeting_date.month, meeting_date.day, 23, 59, 59)

        # Format times in ISO format for calendar API
        processed_input["starttime"] = start_time.isoformat() + "Z"
        processed_input["endtime"] = end_time.isoformat() + "Z"
        processed_input["duration"] = duration_minutes
        processed_input["meeting_date"] = meeting_date.strftime("%Y-%m-%d")

        return processed_input

    def get_calendar_events(self, users, start_time, end_time):
        """Get calendar events for all users"""
        all_events = {}

        for user in users:
            # In a real implementation, this would call the actual calendar API using the provided function
            events = retrive_calendar_events(user, start_time, end_time)
            # events = self.mock_retrieve_calendar_events(user, start_time, end_time)
            all_events[user] = events

        return all_events

    def find_available_slots(self, processed_input):
        """Find available time slots for all attendees"""
        start_time = processed_input["starttime"]
        end_time = processed_input["endtime"]
        duration = processed_input["duration"]
        meeting_date = processed_input["meeting_date"]

        # Get all attendees including the sender
        all_attendees = [processed_input["From"]] + [attendee["email"] for attendee in processed_input["Attendees"]]

        # Get busy times for all attendees
        busy_times = []
        for attendee in all_attendees:
            events = retrive_calendar_events(attendee, start_time, end_time)
            for event in events:
                busy_times.append({
                    "start": datetime.datetime.fromisoformat(event["StartTime"]),
                    "end": datetime.datetime.fromisoformat(event["EndTime"])
                })

        # Sort busy times by start time
        busy_times.sort(key=lambda x: x["start"])

        # Merge overlapping busy times
        merged_busy_times = []
        for busy in busy_times:
            if not merged_busy_times or busy["start"] > merged_busy_times[-1]["end"]:
                merged_busy_times.append(busy)
            else:
                merged_busy_times[-1]["end"] = max(merged_busy_times[-1]["end"], busy["end"])

        # Define working hours (9 AM to 6 PM)
        work_start = datetime.datetime.fromisoformat(f"{meeting_date}T09:00:00")
        work_end = datetime.datetime.fromisoformat(f"{meeting_date}T18:00:00")

        # Find available slots within working hours
        available_slots = []
        current_time = work_start

        for busy in merged_busy_times:
            if busy["start"] > current_time and (busy["start"] - current_time).total_seconds() / 60 >= duration:
                available_slots.append({
                    "start": current_time,
                    "end": busy["start"]
                })
            current_time = max(current_time, busy["end"])

        # Check if there's available time after the last busy period until end of working hours
        if work_end > current_time and (work_end - current_time).total_seconds() / 60 >= duration:
            available_slots.append({
                "start": current_time,
                "end": work_end
            })

        # Format available slots for output
        formatted_slots = []
        for slot in available_slots:
            formatted_slots.append({
                "start": slot["start"].isoformat(),
                "end": slot["end"].isoformat(),
                "duration_minutes": int((slot["end"] - slot["start"]).total_seconds() / 60)
            })

        return formatted_slots

    def get_llm_decision(self, available_slots, processed_input):
        """Simulate LLM to select the best meeting time"""
        duration = processed_input["duration"]

        if not available_slots:
            return {
                "llm_response": "No suitable meeting time found. Please try a different day.",
                "selected_time": None
            }

        # Prefer mid-day slots (around 2 PM)
        target_time = datetime.time(14, 0)

        best_slot = None
        best_score = float('inf')

        for slot in available_slots:
            slot_start = datetime.datetime.fromisoformat(slot["start"])
            slot_time = slot_start.time()

            # Calculate how far this slot is from our target time
            target_minutes = target_time.hour * 60 + target_time.minute
            slot_minutes = slot_time.hour * 60 + slot_time.minute
            time_diff = abs(target_minutes - slot_minutes)

            if time_diff < best_score:
                best_score = time_diff

                # Create a meeting that fits within th*is slot
                meeting_start = slot_start
                meeting_end = meeting_start + timedelta(minutes=duration)

                best_slot = {
                    "start": meeting_start.isoformat(),
                    "end": meeting_end.isoformat(),
                    "duration": duration
                }

        # Format times in a readable way
        start_time = datetime.datetime.fromisoformat(best_slot["start"])
        end_time = datetime.datetime.fromisoformat(best_slot["end"])
        start_time_str = start_time.strftime("%I:%M %p")
        end_time_str = end_time.strftime("%I:%M %p")
        meeting_date_str = start_time.strftime("%A, %B %d, %Y")

        llm_response = f"""
Based on the calendar availability of all attendees, I recommend scheduling the meeting on {meeting_date_str} from {start_time_str} to {end_time_str}.

This time works well because:
1. All attendees are available during this slot
2. It's during standard working hours
3. It allows for the requested {best_slot['duration']} minutes for the meeting

Would you like me to schedule this meeting?
"""

        return {
            "llm_response": llm_response,
            "selected_time": best_slot
        }

    def format_llm_prompt(self, available_slots, processed_input):
        """Format a prompt for the LLM to make a decision"""
        prompt = f"""
You are an AI assistant helping to schedule a meeting. Here's the meeting request:

Subject: {processed_input['Subject']}
From: {processed_input['From']}
Attendees: {', '.join([attendee['email'] for attendee in processed_input['Attendees']])}
Email Content: {processed_input['EmailContent']}

Based on everyone's calendar, here are the available time slots on {processed_input['meeting_date']}:
"""

        for i, slot in enumerate(available_slots, 1):
            start_time = datetime.datetime.fromisoformat(slot["start"])
            end_time = datetime.datetime.fromisoformat(slot["end"])
            start_time_str = start_time.strftime("%I:%M %p")
            end_time_str = end_time.strftime("%I:%M %p")
            prompt += f"{i}. {start_time_str} to {end_time_str} (duration: {slot['duration_minutes']} minutes)\n"

        prompt += f"\nThe meeting requires {processed_input['duration']} minutes. Please select the best time slot and explain your reasoning."

        return prompt

    def create_llm_api_payload(self, prompt):
        """Create the payload for the LLM API"""
        return {
            "model": "/home/user/Models/deepseek-ai/deepseek-llm-7b-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an AI assistant helping to schedule meetings. You need to select the best meeting time based on availability and explain your reasoning."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "stream": False,
            "max_tokens": 256
        }

    def schedule_meeting(self, input_data):
        """Main function to schedule a meeting"""
        # Step 1: Process the input
        processed_input = self.process_email_input(input_data)

        # Step 2: Find available slots
        available_slots = self.find_available_slots(processed_input)

        # Step 3: Get LLM decision (in a real implementation, we would call the LLM API)
        llm_decision = self.get_llm_decision(available_slots, processed_input)

        # Step 4: Format what would be sent to the LLM API
        llm_prompt = self.format_llm_prompt(available_slots, processed_input)
        llm_payload = self.create_llm_api_payload(llm_prompt)

        return {
            "processed_input": processed_input,
            "available_slots": available_slots,
            "llm_decision": llm_decision,
            "llm_api_request": {
                "url": "http://134.199.195.53:5000/v1/chat/completions",
                "headers": {"Content-Type": "application/json"},
                "payload": llm_payload
            }
        }

# Example usage
agent = MeetingSchedulerAgent()

# Sample input data
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

# Schedule the meeting
result = agent.schedule_meeting(input_data)

# Print the results
print("Processed Input:")
print(json.dumps(result["processed_input"], indent=2))

print("\nAvailable Slots:")
print(json.dumps(result["available_slots"], indent=2))

print("\nLLM Decision (Simulated):")
print(json.dumps(result["llm_decision"], indent=2))

output = {

}

# print("\nLLM API Request (What would be sent to the API):")
# print(json.dumps(result["llm_api_request"], indent=2))