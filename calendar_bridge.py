import os
import datetime as dt

from flask import Flask, request, jsonify

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


# ========= CONFIG =========

# ✅ Calendar scope: allows creating & editing events
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# ✅ Put the EXACT name of your OAuth client secret file here
# (the JSON you downloaded from Google Cloud Console)
CLIENT_SECRET_FILE = (
    "client_secret_2_370055681762-1an83limrs9ui5li794lmvpslk35bloj.apps.googleusercontent.com.json"
)

# Token file where OAuth credentials will be cached
TOKEN_FILE = "token.json"

# Default timezone for all events
DEFAULT_TZ = "Asia/Kolkata"

# ==========================


def get_credentials():
    """
    Load / refresh OAuth credentials, or run browser OAuth flow if first time.
    This will create/refresh token.json on disk.
    """
    creds = None

    # Load existing token if it exists
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If there are no valid credentials, refresh or re-authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Try to refresh using the refresh token
            creds.refresh(Request())
        else:
            # First-time login: open browser and ask user to sign in
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials for next time
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def build_calendar_service():
    """
    Build the Google Calendar API service client.
    """
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)
    return service


def add_study_block(summary: str, description: str, start_iso: str, end_iso: str) -> dict:
    """
    Create an event on the user's primary Google Calendar.

    `start_iso` and `end_iso` should be ISO-8601 datetime strings, e.g.:
      "2025-11-20T22:00:00+05:30"

    We always send an explicit timezone field (Asia/Kolkata).
    """
    service = build_calendar_service()

    event = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_iso,
            "timeZone": DEFAULT_TZ,
        },
        "end": {
            "dateTime": end_iso,
            "timeZone": DEFAULT_TZ,
        },
    }

    created = service.events().insert(calendarId="primary", body=event).execute()

    return {
        "ok": True,
        "eventId": created.get("id"),
        "htmlLink": created.get("htmlLink"),
        "summary": created.get("summary"),
        "start": created.get("start"),
        "end": created.get("end"),
    }


def list_events(time_min_iso: str, time_max_iso: str, max_results: int = 10) -> dict:
    """
    List events within a time range.
    """
    service = build_calendar_service()
    
    events_result = service.events().list(
        calendarId='primary', 
        timeMin=time_min_iso,
        timeMax=time_max_iso,
        maxResults=max_results, 
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    
    return {
        "ok": True,
        "events": events
    }


def update_event(event_id: str, summary: str = None, description: str = None, start_iso: str = None, end_iso: str = None) -> dict:
    """
    Update an existing event.
    """
    service = build_calendar_service()
    
    # First get the existing event to preserve fields we aren't changing
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
    except Exception as e:
        return {"ok": False, "error": f"Event not found: {str(e)}"}

    if summary:
        event['summary'] = summary
    if description:
        event['description'] = description
    if start_iso:
        event['start'] = {'dateTime': start_iso, 'timeZone': DEFAULT_TZ}
    if end_iso:
        event['end'] = {'dateTime': end_iso, 'timeZone': DEFAULT_TZ}

    updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()

    return {
        "ok": True,
        "eventId": updated_event.get("id"),
        "htmlLink": updated_event.get("htmlLink"),
        "summary": updated_event.get("summary"),
        "start": updated_event.get("start"),
        "end": updated_event.get("end"),
    }


def delete_event(event_id: str) -> dict:
    """
    Delete an event from the calendar.
    """
    service = build_calendar_service()
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============== FLASK APP ==============

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    """
    Simple health-check endpoint.
    Useful to test if your Flask server is up.
    """
    return jsonify({"ok": True, "message": "calendar_bridge is running"}), 200


@app.route("/create_event", methods=["POST"])
def create_event():
    """
    HTTP endpoint called from your agent_app.py.

    Expected JSON body:
    {
      "summary": "Title",
      "description": "Details",
      "start": "2025-11-20T22:00:00+05:30",
      "end":   "2025-11-20T23:59:00+05:30"
    }
    """
    try:
        data = request.get_json(force=True) or {}

        summary = data.get("summary", "Study Block")
        description = data.get("description", "")
        start = data.get("start")
        end = data.get("end")

        if not start or not end:
            return jsonify(
                {
                    "ok": False,
                    "error": "Missing 'start' or 'end' in request payload.",
                }
            ), 400

        result = add_study_block(summary, description, start, end)
        return jsonify(result), 200

    except Exception as e:
        # Make error visible to the caller (agent_app.py)
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/list_events", methods=["GET"])
def list_events_endpoint():
    """
    HTTP endpoint to list events.
    Query params: timeMin, timeMax, maxResults
    """
    try:
        time_min = request.args.get("timeMin")
        time_max = request.args.get("timeMax")
        max_results = int(request.args.get("maxResults", 10))
        
        if not time_min or not time_max:
             return jsonify({"ok": False, "error": "Missing timeMin or timeMax"}), 400

        result = list_events(time_min, time_max, max_results)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/update_event", methods=["POST"])
def update_event_endpoint():
    """
    HTTP endpoint to update an event.
    JSON body: {eventId, summary, description, start, end}
    """
    try:
        data = request.get_json(force=True) or {}
        event_id = data.get("eventId")
        
        if not event_id:
            return jsonify({"ok": False, "error": "Missing eventId"}), 400
            
        result = update_event(
            event_id,
            summary=data.get("summary"),
            description=data.get("description"),
            start_iso=data.get("start"),
            end_iso=data.get("end")
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/delete_event", methods=["POST"])
def delete_event_endpoint():
    """
    HTTP endpoint to delete an event.
    JSON body: {eventId}
    """
    try:
        data = request.get_json(force=True) or {}
        event_id = data.get("eventId")
        
        if not event_id:
            return jsonify({"ok": False, "error": "Missing eventId"}), 400
            
        result = delete_event(event_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# Optional: quick CLI test when you run:
#   python calendar_bridge.py --test
def quick_test():
    """
    Create a one-off test event directly from this script (no HTTP).
    """
    now = dt.datetime.now()
    start = (now + dt.timedelta(minutes=5)).replace(microsecond=0).isoformat()
    end = (now + dt.timedelta(minutes=65)).replace(microsecond=0).isoformat()

    print("Creating a test event from calendar_bridge.py ...")
    result = add_study_block(
        "CLI Test Block",
        "Sanity check from calendar_bridge.py quick_test()",
        start,
        end,
    )
    print("✅ Result:", result)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test",
        action="store_true",
        help="Create a single test event and exit.",
    )
    args = parser.parse_args()

    if args.test:
        quick_test()
    else:
        # Normal mode: run the Flask server
        print("🚀 Serving Flask app on http://127.0.0.1:5001")
        app.run(host="127.0.0.1", port=5001)
