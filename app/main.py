import os
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query, Header, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.database import init_db, get_garmin_id, save_mapping, get_recent_synced
from app.strava import get_activity_details
from app.garmin import find_garmin_activity_by_start_time, rename_garmin_activity

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize SQLite tables
    init_db()
    print("[Server] Database initialized and server ready.", flush=True)
    yield
    # Shutdown
    print("[Server] Server shutting down.", flush=True)

app = FastAPI(
    title="Strava to Garmin Activity Sync",
    description="Syncs activity title renames from Strava to Garmin Connect.",
    lifespan=lifespan
)

def sync_activity_title(strava_id: int, new_title: str):
    """
    Background worker that matches the Strava activity with Garmin and updates the title.
    """
    print(f"\n[Worker] Processing rename for Strava activity {strava_id} -> '{new_title}'", flush=True)

    # 1. Check local SQLite cache first
    garmin_id = get_garmin_id(strava_id)

    if garmin_id:
        print(f"[Worker] Cache hit: Strava {strava_id} mapped to Garmin {garmin_id}.", flush=True)
    else:
        print(f"[Worker] Cache miss for Strava {strava_id}. Querying Strava API for start time...", flush=True)
        try:
            strava_activity = get_activity_details(strava_id)
            start_date_str = strava_activity.get("start_date") # ISO format: "2026-11-13T08:30:00Z"
            if not start_date_str:
                print(f"[Worker] Error: No start_date in Strava activity payload.", flush=True)
                return

            # Parse ISO UTC timestamp
            # Handles "Z" suffix
            cleaned_date = start_date_str.replace("Z", "+00:00")
            start_datetime = datetime.fromisoformat(cleaned_date)

            # Look up matching Garmin activity
            garmin_id = find_garmin_activity_by_start_time(start_datetime)
            if not garmin_id:
                print(f"[Worker] Could not find a matching Garmin activity around {start_datetime}.", flush=True)
                return

        except Exception as e:
            print(f"[Worker] Failed to query Strava or match with Garmin: {e}", flush=True)
            return

    # 2. Update Garmin Activity Name
    success = rename_garmin_activity(garmin_id, new_title)
    if success:
        # 3. Cache the mapping
        save_mapping(strava_id, garmin_id, new_title)
        print(f"[Worker] Successfully synced Strava {strava_id} <-> Garmin {garmin_id} ('{new_title}')\n", flush=True)

# ---------------------------------------------------------------------------
# Health Check Endpoint
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "activity-sync-python",
        "recent_synced": get_recent_synced(limit=5)
    }

# ---------------------------------------------------------------------------
# Strava Webhook Handshake (GET)
# ---------------------------------------------------------------------------
@app.get("/webhook")
def strava_webhook_challenge(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    """
    Strava requires a one-time challenge-response verification when setting up a subscription.
    """
    expected_token = os.getenv("STRAVA_VERIFY_TOKEN")
    if not expected_token or hub_verify_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification token mismatch"
        )

    print(f"[Webhook] Handshake verified successfully for challenge: {hub_challenge}", flush=True)
    return {"hub.challenge": hub_challenge}

# ---------------------------------------------------------------------------
# Strava Webhook Event Receiver (POST)
# ---------------------------------------------------------------------------
@app.post("/webhook")
async def strava_webhook_event(request: Request, background_tasks: BackgroundTasks):
    """
    Strava delivers activity events here. Strava requires a 200 response within 2 seconds,
    so heavy processing is offloaded to background_tasks.
    """
    payload = await request.json()

    aspect_type = payload.get("aspect_type")
    object_type = payload.get("object_type")
    updates = payload.get("updates", {})
    object_id = payload.get("object_id")

    # We only care when an activity is updated and the title has changed
    if object_type == "activity" and aspect_type == "update" and "title" in updates:
        new_title = updates["title"]
        print(f"[Webhook] Received title update for Strava activity {object_id}: '{new_title}'", flush=True)
        background_tasks.add_task(sync_activity_title, object_id, new_title)
    else:
        # Ignore other events (creates, deletes, or non-title updates)
        pass

    return {"status": "ok"}

# ---------------------------------------------------------------------------
# GitHub CI/CD Auto-Deployment Endpoint (POST)
# ---------------------------------------------------------------------------
@app.post("/deploy")
def trigger_deploy(authorization: Optional[str] = Header(None)):
    """
    Called by GitHub Actions upon merging a PR to update the code on the Pi and restart systemd.
    """
    deploy_secret = os.getenv("DEPLOY_SECRET")
    if not deploy_secret:
        raise HTTPException(status_code=500, detail="DEPLOY_SECRET is not configured on the server.")

    expected_auth = f"Bearer {deploy_secret}"
    if authorization != expected_auth:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized deployment request.")

    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "update.sh"))

    if not os.path.exists(script_path):
        raise HTTPException(status_code=500, detail=f"Update script not found at {script_path}")

    print("[Deploy] Authorized deploy request received. Triggering update script in background...", flush=True)
    subprocess.Popen(["bash", script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return {"status": "Deployment triggered"}
