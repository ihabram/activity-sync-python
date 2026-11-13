import os
import time
import requests
from typing import Optional, Dict, Any

_cached_token: Optional[str] = None
_token_expires_at: int = 0

def get_valid_access_token() -> str:
    """
    Returns a valid Strava access token, refreshing it if expired.
    Strava access tokens typically expire after 6 hours.
    """
    global _cached_token, _token_expires_at

    # If cached token is valid for at least another 5 minutes, use it
    if _cached_token and time.time() < (_token_expires_at - 300):
        return _cached_token

    client_id = os.getenv("STRAVA_CLIENT_ID")
    client_secret = os.getenv("STRAVA_CLIENT_SECRET")
    refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        raise ValueError("Missing Strava credentials in environment (STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN)")

    print("[Strava] Refreshing access token...", flush=True)
    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=15
    )
    response.raise_for_status()
    data = response.json()

    _cached_token = data["access_token"]
    _token_expires_at = data["expires_at"]

    # If Strava returns a new refresh token, update in memory
    new_refresh = data.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        os.environ["STRAVA_REFRESH_TOKEN"] = new_refresh

    print("[Strava] Token refreshed successfully.", flush=True)
    return _cached_token

def get_activity_details(activity_id: int) -> Dict[str, Any]:
    """
    Fetch activity metadata from Strava (including start time and current title).
    """
    access_token = get_valid_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()
