# Strava to Garmin Activity Sync — End-to-End Implementation Plan

A lightweight, automated service designed to run on a **Raspberry Pi Zero W** (~100 MB RAM footprint). 

When you rename an activity in Strava, Strava emits a webhook, this service catches it, finds the corresponding activity in Garmin Connect by timestamp, renames it in Garmin, and caches the mapping in SQLite.

---

## 🏗️ Architecture Overview

```
[ Strava App / Web ]
       ↓ (Renames activity)
[ Strava Webhook Event ]
       ↓ (HTTPS POST)
[ Cloudflare Tunnel ] (Encrypted link from internet to Pi)
       ↓
[ Raspberry Pi Zero W ]
       ├── FastAPI Webhook Listener (Port 8000)
       ├── SQLite DB (Stores Strava-to-Garmin ID mapping)
       └── garminconnect (Updates Garmin Activity title)
```

### Automated GitHub Deployment Flow
```
[ Git Push / PR Merge to main ]
       ↓
[ GitHub Actions (.github/workflows/deploy.yml) ]
       ↓ (HTTPS POST with secret token)
[ Pi /deploy Endpoint ] ──> Runs: git pull && systemctl restart activity-sync
```

---

## 📋 The 7 Phases to Complete the Project

### Phase 1: Application Code & Structure
Create the lightweight Python service with the following file structure:

```text
activity-sync-python/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app (handles /webhook and /deploy)
│   ├── strava.py        # Strava OAuth token refresh & activity details
│   ├── garmin.py        # Garmin login, session caching & activity rename
│   └── database.py      # SQLite operations (strava_id <-> garmin_id mapping)
├── scripts/
│   └── update.sh        # Deployment script called by the /deploy endpoint
├── .github/
│   └── workflows/
│       └── deploy.yml   # Auto-deployment on PR merge
├── .env.example         # Template for environment variables
├── requirements.txt     # Minimal dependencies
└── README.md
```

#### Key Dependencies (`requirements.txt`)
* `fastapi` & `uvicorn[standard]` — High performance, lightweight webhook server.
* `garminconnect` — Open-source library handling Garmin SSO, sessions, and activity renaming.
* `requests` — For Strava OAuth token refreshing and API calls.
* `python-dotenv` — For managing environment secrets.

---

### Phase 2: Credentials & API Setup

#### 1. Strava API Credentials
1. Go to [Strava API Settings](https://www.strava.com/settings/api).
2. Create an API application:
   * **Application Name:** `Activity Sync`
   * **Authorization Callback Domain:** `localhost` (or your future Cloudflare domain)
3. Note down:
   * `STRAVA_CLIENT_ID`
   * `STRAVA_CLIENT_SECRET`
4. Perform an initial OAuth authorization with `activity:read_all` scope to get your long-lived `STRAVA_REFRESH_TOKEN`.

#### 2. Garmin Credentials
* `GARMIN_EMAIL`
* `GARMIN_PASSWORD`
* `garminconnect` automatically creates and persists session tokens in a local folder (`~/.garminconnect`) so you only authenticate once and do not trigger CAPTCHAs or 2FA on every webhook.

#### 3. Webhook Secrets
* `STRAVA_VERIFY_TOKEN` — A custom random string of your choice to verify Strava's initial handshake.
* `DEPLOY_SECRET` — A custom secret token to authorize GitHub Actions deployments.

---

### Phase 3: Domain Logic Implementation

1. **Strava Webhook Handshake (`GET /webhook`)**:
   * Strava sends `hub.challenge`, `hub.verify_token`, and `hub.mode`.
   * Return `{"hub.challenge": hub.challenge}` if `hub.verify_token` matches.

2. **Strava Event Handler (`POST /webhook`)**:
   * Check if `aspect_type == "update"` and `"title"` exists in `updates`.
   * Check SQLite cache: has this `strava_id` already been mapped to a `garmin_id`?
     * **If yes:** Immediately call `garmin.set_activity_name(garmin_id, new_title)`.
     * **If no:** 
       1. Call Strava API to get activity start time (`start_date_local`).
       2. Query Garmin activities for that date (within a ±5 minute window).
       3. Rename the matching Garmin activity.
       4. Save `(strava_id, garmin_id)` in SQLite for instant future edits.

---

### Phase 4: Raspberry Pi Setup

1. **Clone & Virtualenv**:
   ```bash
   cd /home/pi
   git clone <your-repo-url> activity-sync-python
   cd activity-sync-python
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Systemd Service (`/etc/systemd/system/activity-sync.service`)**:
   Ensures the service runs on boot and restarts automatically if it ever crashes:
   ```ini
   [Unit]
   Description=Strava to Garmin Activity Sync
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/activity-sync-python
   EnvironmentFile=/home/pi/activity-sync-python/.env
   ExecStart=/home/pi/activity-sync-python/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
   Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now activity-sync
   ```

---

### Phase 5: Exposing to the Internet (Cloudflare Tunnel)

Strava requires a public HTTPS URL with valid SSL to deliver webhooks. 

1. Install `cloudflared` on the Pi Zero W (ARMv6 release):
   ```bash
   curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm.deb
   sudo dpkg -i cloudflared.deb
   ```
2. Log in and route your tunnel:
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create activity-sync
   cloudflared tunnel route dns activity-sync strava.yourdomain.com
   ```
3. Point the tunnel configuration to `http://localhost:8000`.
4. Install it as a system service: `sudo cloudflared service install`.

*(Alternative: You can also use a Cloudflare Quick Tunnel if you don't own a custom domain).*

---

### Phase 6: Strava Webhook Subscription

Once your Cloudflare URL is live and pointing to your Pi, register the subscription with Strava:

```bash
curl -X POST https://www.strava.com/api/v3/push_subscriptions \
  -F client_id=YOUR_STRAVA_CLIENT_ID \
  -F client_secret=YOUR_STRAVA_CLIENT_SECRET \
  -F callback_url=https://strava.yourdomain.com/webhook \
  -F verify_token=YOUR_STRAVA_VERIFY_TOKEN
```

Strava immediately calls `GET https://strava.yourdomain.com/webhook` to verify, receives the challenge response, and activates the webhook!

---

### Phase 7: GitHub CI/CD Auto-Deployment

1. Store repository secrets in GitHub:
   * `DEPLOY_URL` = `https://strava.yourdomain.com/deploy`
   * `DEPLOY_SECRET` = *(matching secret from your `.env`)*

2. Whenever a PR is merged into `main`, GitHub Actions calls:
   ```bash
   curl -X POST ${{ secrets.DEPLOY_URL }} \
     -H "Authorization: Bearer ${{ secrets.DEPLOY_SECRET }}"
   ```

3. The Pi's `scripts/update.sh` runs:
   ```bash
   #!/bin/bash
   cd /home/pi/activity-sync-python
   git pull origin main
   source venv/bin/activate
   pip install -r requirements.txt
   sudo systemctl restart activity-sync
   ```

---

## 🎯 Verification & Testing Checklist

- [ ] Webhook validation test: `curl https://strava.yourdomain.com/webhook?hub.challenge=test&hub.verify_token=YOUR_TOKEN` returns `{"hub.challenge":"test"}`.
- [ ] Record or open an existing test activity in Strava and edit its name.
- [ ] Check Pi logs: `sudo journalctl -u activity-sync -f`.
- [ ] Confirm the new name appears in the Garmin Connect app.
- [ ] Push a small commit to GitHub and verify the Pi automatically pulls and restarts.
