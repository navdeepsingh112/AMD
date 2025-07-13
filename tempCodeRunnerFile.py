es:
    #     # If no one has any events, the entire range is free if it's long enough
    #     start_dt = datetime.fromisoformat(start_time_str)
    #     end_dt = datetime.fromisoformat(end_time_str)
    #     if (end_dt - start_dt) >= timedelta(minutes=duration_minutes):
    #         return [{'start': start_time_str, 'end': end_time_str}]
    #     else:
    #         return []