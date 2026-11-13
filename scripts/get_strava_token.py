#!/usr/bin/env python3
"""
Helper script to generate your initial Strava Refresh Token with 'activity:read_all' permissions.

How to use:
1. Ensure your Strava API Application (https://www.strava.com/settings/api) has:
   Authorization Callback Domain: localhost
2. Run this script:
   python scripts/get_strava_token.py
"""

import urllib.parse
import requests

def main():
    print("=" * 60)
    print("Strava OAuth Token Generator")
    print("=" * 60)

    client_id = input("Enter your Strava Client ID: ").strip()
    client_secret = input("Enter your Strava Client Secret: ").strip()

    if not client_id or not client_secret:
        print("Error: Client ID and Secret are required.")
        return

    # Step 1: Generate Authorization URL
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": "http://localhost",
        "approval_prompt": "force",
        "scope": "activity:read_all",
    }
    auth_url = f"https://www.strava.com/oauth/authorize?{urllib.parse.urlencode(params)}"

    print("\n1. Open this URL in your web browser:")
    print("-" * 60)
    print(auth_url)
    print("-" * 60)
    print("\n2. Click 'Authorize' on the Strava page.")
    print("3. Your browser will redirect to an address starting with:")
    print("   http://localhost/?state=&code=XXXXXXXXXXXX&scope=activity:read_all")
    print("   (The page will say 'Site can't be reached', which is completely normal!)")

    code_input = input("\n4. Copy the entire redirected URL or just the 'code' parameter value here: ").strip()

    if "code=" in code_input:
        # Extract code from URL query string
        parsed = urllib.parse.urlparse(code_input)
        query_params = urllib.parse.parse_qs(parsed.query)
        code = query_params.get("code", [""])[0]
    else:
        code = code_input

    if not code:
        print("Error: Could not extract authorization code.")
        return

    # Step 2: Exchange code for refresh token
    print("\nExchanging code for tokens...")
    res = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=15
    )

    if res.status_code != 200:
        print(f"Failed to exchange code: {res.status_code} {res.text}")
        return

    data = res.json()
    refresh_token = data.get("refresh_token")

    print("\n" + "=" * 60)
    print("SUCCESS! Add these to your .env file:")
    print("=" * 60)
    print(f"STRAVA_CLIENT_ID={client_id}")
    print(f"STRAVA_CLIENT_SECRET={client_secret}")
    print(f"STRAVA_REFRESH_TOKEN={refresh_token}")
    print("=" * 60)

if __name__ == "__main__":
    main()
