# Activity Sync (Python)

Sync activity renames from **Strava** to **Garmin Connect** automatically using Strava Webhooks. 

Lightweight and resource-friendly, designed to run 24/7 on a **Raspberry Pi Zero W** (~100 MB RAM total footprint).

---

## 📖 Quick Links

* **[Complete Setup & Implementation Guide (STEPS.md)](file:///Users/I755543/learning/activity-sync-python/STEPS.md)** — Step-by-step roadmap from code to Raspberry Pi deployment and automated CI/CD.

---

## 🛠️ Tech Stack

* **Language:** Python 3.11+
* **Framework:** FastAPI + Uvicorn
* **Database:** SQLite (embedded)
* **Libraries:** `garminconnect`, `requests`, `python-dotenv`
* **Tunnel:** Cloudflare Tunnel (`cloudflared`)
* **Host:** Raspberry Pi Zero W (systemd service)
* **CI/CD:** GitHub Actions (auto-deploy on PR merge)
