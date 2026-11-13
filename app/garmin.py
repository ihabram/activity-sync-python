import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from garminconnect import Garmin, GarminConnectAuthenticationError

_garmin_client: Optional[Garmin] = None

def get_tokenstore_path() -> Path:
    custom_path = os.getenv("GARMIN_TOKENSTORE_DIR")
    if custom_path:
        p = Path(custom_path)
    else:
        p = Path.home() / ".garminconnect"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_garmin_client() -> Garmin:
    """
    Returns an authenticated Garmin client using tokenstore caching to avoid repeated logins.
    """
    global _garmin_client
    if _garmin_client is not None:
        return _garmin_client

    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    tokenstore = get_tokenstore_path()

    # 1. Try loading cached session tokens
    try:
        print(f"[Garmin] Attempting login with cached session at {tokenstore}...", flush=True)
        client = Garmin()
        client.login(tokenstore=str(tokenstore))
        print("[Garmin] Session restored successfully from cache.", flush=True)
        _garmin_client = client
        return _garmin_client
    except (GarminConnectAuthenticationError, Exception) as e:
        print(f"[Garmin] Cached session invalid or missing: {e}. Logging in with credentials...", flush=True)

    # 2. Fall back to credentials
    if not email or not password:
        raise ValueError("GARMIN_EMAIL and GARMIN_PASSWORD must be configured in environment.")

    client = Garmin(email=email, password=password)
    client.login()

    # Save tokens to disk for future executions
    try:
        client.garth.dump(str(tokenstore))
        print(f"[Garmin] Saved fresh session tokens to {tokenstore}.", flush=True)
    except Exception as e:
        print(f"[Garmin] Warning: Could not save session tokens: {e}", flush=True)

    _garmin_client = client
    return _garmin_client

def find_garmin_activity_by_start_time(start_datetime_utc: datetime, tolerance_minutes: int = 15) -> Optional[int]:
    """
    Searches Garmin activities within a date window to find the one matching the given UTC start time.
    Returns the Garmin activityId if found, else None.
    """
    client = get_garmin_client()

    # Query a 2-day window around the target date to avoid timezone border mismatches
    start_date = (start_datetime_utc - timedelta(days=1)).strftime("%Y-%m-%d")
    end_date = (start_datetime_utc + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"[Garmin] Querying activities between {start_date} and {end_date}...", flush=True)
    try:
        activities = client.get_activities_by_date(start_date, end_date)
    except Exception as e:
        print(f"[Garmin] Error fetching activities by date: {e}", flush=True)
        return None

    if not activities:
        print("[Garmin] No activities found in date window.", flush=True)
        return None

    target_ts = start_datetime_utc.timestamp()

    best_match_id = None
    min_diff_seconds = tolerance_minutes * 60

    for act in activities:
        # Garmin provides startTimeGMT formatted as "YYYY-MM-DD HH:MM:SS"
        gmt_str = act.get("startTimeGMT")
        if not gmt_str:
            continue

        try:
            act_time = datetime.strptime(gmt_str, "%Y-%m-%d %H:%M:%S")
            diff = abs(act_time.timestamp() - target_ts)
            if diff < min_diff_seconds:
                min_diff_seconds = diff
                best_match_id = act.get("activityId")
        except Exception as e:
            continue

    if best_match_id:
        print(f"[Garmin] Found matching activity {best_match_id} (time delta: {int(min_diff_seconds)}s)", flush=True)
    else:
        print(f"[Garmin] No activity matched within {tolerance_minutes} minutes tolerance.", flush=True)

    return best_match_id

def rename_garmin_activity(activity_id: int, new_title: str) -> bool:
    """
    Updates the title of the Garmin activity.
    """
    client = get_garmin_client()
    print(f"[Garmin] Renaming activity {activity_id} to '{new_title}'...", flush=True)
    try:
        client.set_activity_name(activity_id, new_title)
        print(f"[Garmin] Successfully renamed activity {activity_id}!", flush=True)
        return True
    except Exception as e:
        print(f"[Garmin] Error renaming activity {activity_id}: {e}", flush=True)
        return False
