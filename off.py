from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from datetime import datetime
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
print(get_gmt_offset("New York"))   # -> "-04:00"
print(get_gmt_offset("New Delhi"))  # -> "+05:30"
print(get_gmt_offset("Tokyo"))      # -> "+09:00"
