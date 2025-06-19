import requests
import pandas as pd
from datetime import datetime
import os
import time  # for paginating notification calls
import re  # regex for robust text parsing of notification amounts

# --- CONFIGURATION ---

EMAIL = "YOUR-LOGIN"          # <- Replace with your SurePet login email
PASSWORD = "YOUR-PASSWORD"        # <- Replace with your SurePet password
DEVICE_ID = "0123456789"          # <- Static value, okay to leave as-is
START_DATE = "2025-01-01"         # <- First date to pull data from
END_DATE = datetime.utcnow().date().isoformat()  # <- Up to today in UTC
OUTPUT_PATH = "WHERE-YOU-WANT-TO-SAVE-IT-surepet_events.csv"

# --- NOTIFICATIONS CONFIGURATION ---
ALERT_PAGE_SIZE = 25    # number of notifications per page (25 default)
ALERT_MAX_PAGES = 40    # number of pages to fetch (~1000 alerts total)
# Map from alert device names to numeric device IDs
# Used if you have fountains that don't always tag a drinking event to a microchip

ALERT_DEVICE_MAP = {
    "Fountain 1": 555555,
    "Fountain 2": 555555
}

# --- AUTHENTICATION ---

def get_token():
    url = "https://app.api.surehub.io/api/auth/login"
    headers = {"Content-Type": "application/json"}
    payload = {
        "email_address": EMAIL,
        "password": PASSWORD,
        "device_id": DEVICE_ID
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()["data"]["token"]

# --- FETCH PETS AND HOUSEHOLD ---

def get_pets_and_household(token):
    url = "https://app.api.surehub.io/api/pet"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    pets = response.json()["data"]
    household_id = pets[0]["household_id"] if pets else None
    return pets, household_id

# --- FETCH AGGREGATE EVENTS ---

def get_pet_report(token, household_id, pet_id, from_date, to_date):
    url = f"https://app.api.surehub.io/api/report/household/{household_id}/pet/{pet_id}/aggregate"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"from": from_date, "to": to_date}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()["data"]

# --- TRANSFORM TO DESIRED FORMAT ---

def parse_event_data(events_dict, pet_id, pet_name, endpoint):
    parsed = []
    now = datetime.utcnow().isoformat()

    for event_type, section in events_dict.items():
        records = section.get("datapoints", [])
        if not isinstance(records, list):
            continue
        for entry in records:
            if not isinstance(entry, dict):
                continue
            timestamp = entry.get("to")
            duration = entry.get("duration")
            weights = entry.get("weights", [])
            amount = weights[0]["change"] if weights and isinstance(weights[0], dict) and "change" in weights[0] else None
            device_id = entry.get("device_id")
            context = entry.get("context")
            if event_type == "feeding":
                typ = "Food"
            elif event_type == "drinking":
                typ = "Water"
            elif event_type == "movement":
                typ = "Movement"
            else:
                typ = "Unknown"

            parsed.append({
                "Recorded At": now,
                "Pet ID": pet_id,
                "Pet Name": pet_name or "Primary",
                "Type": typ,
                "Amount": amount,
                "Timestamp": timestamp,
                "Duration": duration,
                "Device ID": device_id,
                "Context": context,
                "Endpoint": endpoint
            })
    return parsed

# --- FETCH AND PARSE NOTIFICATIONS (ALERTS) ---
# Added to pull water events that weren't assigned to a microchip
# Sadly they must be paginated to run through, easier to fetch these records from alerts vs. events/timeline history


def fetch_notifications(token):
    """
    Fetch up to ALERT_PAGE_SIZE * ALERT_MAX_PAGES alerts from the /notification endpoint.
    Uses pagination to avoid timeouts/rate limits.
    Rationale: retrieving human-friendly water-consumption alerts
    complements structured pet-report data.
    """
    url = "https://app.api.surehub.io/api/notification"
    headers = {"Authorization": f"Bearer {token}"}
    notifications = []
    for page in range(1, ALERT_MAX_PAGES + 1):
        params = {"page": page, "page_size": ALERT_PAGE_SIZE}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        batch = response.json().get("data", [])
        if not batch:
            break  # no more alerts
        notifications.extend(batch)
        print(f"→ Collected {len(notifications)} notifications so far...")
        time.sleep(2)  # throttle to avoid 429 rate limits
    return notifications

def parse_notifications_data(notifications):
    """
    Convert raw notification alerts into event dicts matching parse_event_data schema.
    Extracts numeric amount and device info from the alert text.
    """
    parsed = []
    now = datetime.utcnow().isoformat()
    for note in notifications:
        # Skip non-water alerts (e.g., type 32 = maintenance reminders)
        if note.get("type") != 34:
            continue
        text = note.get("text", "")
        # Extract the volume (integer ml) from the start of text, handling non-breaking spaces
        match = re.match(r"^(\d+)", text)
        # Use a negative amount for notifications to indicate water removed
        amount = -int(match.group(1)) if match else None
        # Extract the device name after 'from', if present
        parts = text.split(" from ", 1)
        device_name = parts[1].strip() if len(parts) == 2 else text
        device_id = ALERT_DEVICE_MAP.get(device_name)
        parsed.append({
            "Recorded At": now,
            "Pet ID": device_id,
            "Pet Name": device_name,
            "Type": "Water",
            "Amount": amount,
            "Timestamp": note.get("created_at"),
            "Duration": "",
            "Device ID": device_id,
            "Context": 1,
            "Endpoint": "/api/notification"
        })
    return parsed

# --- MAIN SCRIPT ---

def main():
    print("Logging in...")
    token = get_token()

    print("Getting pets and household ID...")
    pets, household_id = get_pets_and_household(token)

    all_events = []
    for pet in pets:
        pet_id = pet["id"]
        pet_name = pet["name"]
        print(f"Pulling data for {pet_name}...")
        events = get_pet_report(token, household_id, pet_id, START_DATE, END_DATE)
        print(f"  → Received {len(events)} raw events")
        print(f"  → Type: {type(events)}")
        if isinstance(events, list):
            print(f"  → Sample: {events[:3]}")
        elif isinstance(events, dict):
            print(f"  → Keys: {list(events.keys())}")
            for key in events:
                records = events[key]
                if isinstance(records, list):
                    print(f"    {key}: {len(records)} record(s)")
                    if len(records) > 0 and isinstance(records[0], dict):
                        print(f"    Sample {key} event: {records[0]}")
                        if key == "movement" and len(records) > 1:
                            print(f"    Another movement event: {records[1]}")
        else:
            print(f"  → Raw: {events}")
        report_endpoint = f"/api/report/household/{household_id}/pet/{pet_id}/aggregate?from={START_DATE}&to={END_DATE}"
        parsed = parse_event_data(events, pet_id, pet_name, report_endpoint)
        all_events.extend(parsed)

    # --- INCLUDE ALERTS AS WATER EVENTS ---
    print("Fetching notification alerts...")
    notifications = fetch_notifications(token)
    print(f"Parsing {len(notifications)} notifications into events...")
    alert_events = parse_notifications_data(notifications)
    all_events.extend(alert_events)

    print(f"Writing {len(all_events)} events to CSV...")
    df = pd.DataFrame(all_events)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"✅ Done! File saved to:\n{OUTPUT_PATH}")

if __name__ == "__main__":
    main()
