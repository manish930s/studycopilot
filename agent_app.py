import os
import datetime as dt
from zoneinfo import ZoneInfo
import requests
import re
import google.generativeai as genai
from google.generativeai import types as genai_types
from dotenv import load_dotenv

load_dotenv()

# ========================

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("Please set the GOOGLE_API_KEY environment variable first.")

genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-2.0-flash"   # or "gemini-2.5-flash-lite" if enabled
model = genai.GenerativeModel(MODEL_NAME)

# URL of your local Flask bridge (no Cloudflare)
CALENDAR_BRIDGE_URL = "http://127.0.0.1:5001/create_event"

# ========================
# Timezone helpers
# ========================

def get_ist_tz() -> dt.tzinfo:
    """
    Safely get Asia/Kolkata timezone.

    - Tries ZoneInfo('Asia/Kolkata')
    - If tzdata is missing, falls back to fixed +05:30 offset
    """
    try:
        return ZoneInfo("Asia/Kolkata")
    except Exception:
        # No tzdata on this system – use fixed IST offset (good enough, no DST).
        return dt.timezone(dt.timedelta(hours=5, minutes=30))


# ========================
# Tools
# ========================

def get_current_datetime(timezone: str = "Asia/Kolkata") -> dict:
    """
    Returns current date/time so we can:
    - know today's date
    - answer "what is today"
    - interpret "tomorrow", etc.
    """
    if timezone == "Asia/Kolkata":
        tz = get_ist_tz()
    else:
        try:
            tz = ZoneInfo(timezone)
        except Exception:
            tz = get_ist_tz()

    now = dt.datetime.now(tz)

    return {
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "weekday": now.strftime("%A"),
        "human_readable": now.strftime("%A, %d %B %Y, %I:%M %p"),
        "timezone": timezone,
    }


def create_calendar_event(summary: str, description: str, start_iso: str, end_iso: str) -> dict:
    """
    Call your local calendar_bridge.py server (Flask) to create an event.

    Args:
        summary: event title
        description: event description
        start_iso: ISO 8601 string (with timezone)
        end_iso: ISO 8601 string
    """
    payload = {
        "summary": summary,
        "description": description,
        "start": start_iso,
        "end": end_iso,
    }

    try:
        resp = requests.post(CALENDAR_BRIDGE_URL, json=payload, timeout=10)
        print("[DEBUG] Calendar bridge status:", resp.status_code)
        print("[DEBUG] Calendar bridge body  :", resp.text)

        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


def list_calendar_events(time_min_iso: str, time_max_iso: str, max_results: int = 10) -> dict:
    """
    Call local calendar_bridge to list events.
    """
    params = {
        "timeMin": time_min_iso,
        "timeMax": time_max_iso,
        "maxResults": max_results
    }
    try:
        # Construct URL for GET request
        url = CALENDAR_BRIDGE_URL.replace("/create_event", "/list_events")
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


def update_calendar_event(event_id: str, summary: str = None, description: str = None, start_iso: str = None, end_iso: str = None) -> dict:
    """
    Call local calendar_bridge to update an event.
    """
    payload = {
        "eventId": event_id,
        "summary": summary,
        "description": description,
        "start": start_iso,
        "end": end_iso
    }
    try:
        # Construct URL for POST request
        url = CALENDAR_BRIDGE_URL.replace("/create_event", "/update_event")
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ========================
# Helper: auto-parse "tomorrow at 11pm"
# ========================

def auto_create_tomorrow_event(user_message: str, today_info: dict) -> dict | None:
    """
    Very simple 'direct save' helper.

    If user says things like:
      "i want to save reminder for DSA task tomorrow at 11pm"

    We:
      - detect "tomorrow"
      - parse "11pm"
      - build IST datetimes for tomorrow 23:00–23:30
      - call create_calendar_event()
    """
    text = user_message.lower()

    if "tomorrow" not in text:
        return None

    # find time like '11pm', '7 am', '07:30pm'
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text)
    if not m:
        # no recognizable time – let manual flow handle it
        return None

    hour = int(m.group(1))
    minute = int(m.group(2) or "0")
    ampm = m.group(3)

    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    # figure out "tomorrow" date from today's date
    # today_info['date'] is "YYYY-MM-DD"
    today_date = dt.datetime.fromisoformat(today_info["date"] + "T00:00:00")
    ist = get_ist_tz()
    today_date = today_date.replace(tzinfo=ist)

    start_dt = today_date + dt.timedelta(days=1, hours=hour, minutes=minute)
    end_dt = start_dt + dt.timedelta(minutes=30)  # default 30-minute reminder

    # crude summary guess from text
    summary = "Reminder"
    if "dsa" in text:
        summary = "DSA Task Reminder"
    elif "gym" in text:
        summary = "GYM"
    elif "exam" in text:
        summary = "Exam Prep"

    description = user_message

    calendar_result = create_calendar_event(
        summary=summary,
        description=description,
        start_iso=start_dt.isoformat(),
        end_iso=end_dt.isoformat(),
    )

    return {
        "calendar_result": calendar_result,
        "summary": summary,
        "start_dt": start_dt,
        "end_dt": end_dt,
    }


# ========================
# Helper: ask Gemini
# ========================

# ========================
# Helper: ask Gemini
# ========================

SYSTEM_PROMPT = """
You are Manish's personal Study & Career Co-Pilot.

Capabilities:
- Help plan study, AI/ML learning, Kaggle competitions, MCA exam prep.
- You know how to reason about today's date and relative dates using the `get_current_datetime` tool.
- You can create Google Calendar events via the `create_calendar_event` tool.
- You can LIST events using `list_calendar_events` and UPDATE them using `update_calendar_event`.

VERY IMPORTANT:

1) When the user asks for the current date/day:
   - The wrapper passes today's date/time in [CONTEXT]. Use that to answer.

2) When the user says things like:
   - "tomorrow", "day after tomorrow", "next Monday", "this weekend"
   - or specific dates like "20th Nov 2025"
   you must interpret them into concrete datetimes in IST (Asia/Kolkata).

3) There are THREE ways to interact with the calendar:

   (A) Direct auto-save (Creation):
       The Python wrapper may already have created an event and will pass details in [CONTEXT]
       under 'auto_event_info'. In that case, just confirm what was done.

   (B) Manual wizard (Creation):
       If the wrapper sets 'manual_calendar_flow' in [CONTEXT], then you should speak like
       a conversational wizard while Python collects the exact date/time from the user.
   
   (C) Rescheduling / Updating (CRITICAL):
       If the user wants to reschedule, you might need to ask for clarification first.
       Once you are sure about the Event ID and the new Start/End times (in IST), you MUST output a JSON block at the end of your response to trigger the update.
       
       IMPORTANT: 'eventId' must be the actual Google Calendar ID string (e.g., "7vgnurdqdpe85km0ofnb061b08"), NOT the event title/summary.
       
       Format:
       ```json
       {
         "action": "update_event",
         "eventId": "EVENT_ID_HERE",
         "start_iso": "2025-MM-DDTHH:MM:00+05:30",
         "end_iso": "2025-MM-DDTHH:MM:00+05:30"
       }
       ```

   (D) Batch Creation (Planning):
       If the user asks you to "schedule this plan" or "save these events", and you have just generated a list of tasks/events with times, you can create them all at once.
       Output a JSON block with action "create_events" (plural) and a list of events.
       
       IMPORTANT: If the plan has vague times like "Morning", "Afternoon", "Evening", YOU MUST INFER CONCRETE TIMES based on the user's preferences or defaults:
       - Morning: 10:00 AM
       - Afternoon: 2:00 PM
       - Evening: 6:00 PM
       
       Do NOT ask the user for times again if they said "schedule it". Just pick reasonable defaults and generate the JSON.
       
       Format:
       ```json
       {
         "action": "create_events",
         "events": [
           {
             "summary": "Python Basics",
             "description": "Variables, Data Types",
             "start_iso": "2025-11-20T10:00:00+05:30",
             "end_iso": "2025-11-20T11:30:00+05:30"
           },
           {
             "summary": "NumPy Intro",
             "description": "Basic arrays",
             "start_iso": "2025-11-20T12:00:00+05:30",
             "end_iso": "2025-11-20T13:00:00+05:30"
           }
         ]
       }
       ```

4) You DO NOT directly call Python functions. They are already called outside and results are put in [CONTEXT]. 
   EXCEPTION: For updating events or batch creating events, you use the JSON format above.
"""


def chat_with_agent(user_message: str, history: list[dict], context: dict | None = None) -> str:
    """
    Send a message to Gemini with history and extra context.
    """
    parts = []

    # System prompt
    parts.append(genai_types.Part(text=SYSTEM_PROMPT))

    # Add context (like today's date, calendar results, etc.)
    if context:
        parts.append(
            genai_types.Part(
                text=f"[SYSTEM CONTEXT]\n{context}"
            )
        )

    # Add History
    # We'll format history as a transcript for the model to see previous turns
    history_text = ""
    for turn in history:
        role = turn["role"]
        content = turn["content"]
        history_text += f"[{role.upper()}]: {content}\n"
    
    if history_text:
        parts.append(genai_types.Part(text=f"[CONVERSATION HISTORY]\n{history_text}"))

    # User message
    parts.append(genai_types.Part(text=f"[USER]\n{user_message}"))

    content = genai_types.Content(
        role="user",
        parts=parts
    )

    try:
        resp = client.models.generate_content(
            model=MODEL_NAME,
            contents=[content],
        )

        # Extract text
        if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
            text = resp.candidates[0].content.parts[0].text
            if text is not None:
                return text.strip()
    except Exception as e:
        return f"(Error calling Gemini: {e})"

    return "(No response from model)"

    if "tomorrow" not in text:
        return None

    # find time like '11pm', '7 am', '07:30pm'
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text)
    if not m:
        # no recognizable time – let manual flow handle it
        return None

    hour = int(m.group(1))
    minute = int(m.group(2) or "0")
    ampm = m.group(3)

    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    # figure out "tomorrow" date from today's date
    # today_info['date'] is "YYYY-MM-DD"
    today_date = dt.datetime.fromisoformat(today_info["date"] + "T00:00:00")
    ist = get_ist_tz()
    today_date = today_date.replace(tzinfo=ist)

    start_dt = today_date + dt.timedelta(days=1, hours=hour, minutes=minute)
    end_dt = start_dt + dt.timedelta(minutes=30)  # default 30-minute reminder

    # crude summary guess from text
    summary = "Reminder"
    if "dsa" in text:
        summary = "DSA Task Reminder"
    elif "gym" in text:
        summary = "GYM"
    elif "exam" in text:
        summary = "Exam Prep"

    description = user_message

    calendar_result = create_calendar_event(
        summary=summary,
        description=description,
        start_iso=start_dt.isoformat(),
        end_iso=end_dt.isoformat(),
    )

    return {
        "calendar_result": calendar_result,
        "summary": summary,
        "start_dt": start_dt,
        "end_dt": end_dt,
    }


# ========================
# Helper: ask Gemini
# ========================

# ========================
# Helper: ask Gemini
# ========================

SYSTEM_PROMPT = """
You are Manish's personal Study & Career Co-Pilot.

Capabilities:
- Help plan study, AI/ML learning, Kaggle competitions, MCA exam prep.
- You know how to reason about today's date and relative dates using the `get_current_datetime` tool.
- You can create Google Calendar events via the `create_calendar_event` tool.
- You can LIST events using `list_calendar_events` and UPDATE them using `update_calendar_event`.

VERY IMPORTANT:

1) When the user asks for the current date/day:
   - The wrapper passes today's date/time in [CONTEXT]. Use that to answer.

2) When the user says things like:
   - "tomorrow", "day after tomorrow", "next Monday", "this weekend"
   - or specific dates like "20th Nov 2025"
   you must interpret them into concrete datetimes in IST (Asia/Kolkata).

3) There are THREE ways to interact with the calendar:

   (A) Direct auto-save (Creation):
       The Python wrapper may already have created an event and will pass details in [CONTEXT]
       under 'auto_event_info'. In that case, just confirm what was done.

   (B) Manual wizard (Creation):
       If the wrapper sets 'manual_calendar_flow' in [CONTEXT], then you should speak like
       a conversational wizard while Python collects the exact date/time from the user.
   
   (C) Rescheduling / Updating (CRITICAL):
       If the user wants to reschedule, you might need to ask for clarification first.
       Once you are sure about the Event ID and the new Start/End times (in IST), you MUST output a JSON block at the end of your response to trigger the update.
       
       IMPORTANT: 'eventId' must be the actual Google Calendar ID string (e.g., "7vgnurdqdpe85km0ofnb061b08"), NOT the event title/summary.
       
       Format:
       ```json
       {
         "action": "update_event",
         "eventId": "EVENT_ID_HERE",
         "start_iso": "2025-MM-DDTHH:MM:00+05:30",
         "end_iso": "2025-MM-DDTHH:MM:00+05:30"
       }
       ```

   (D) Batch Creation (Planning):
       If the user asks you to "schedule this plan" or "save these events", and you have just generated a list of tasks/events with times, you can create them all at once.
       Output a JSON block with action "create_events" (plural) and a list of events.
       
       IMPORTANT: If the plan has vague times like "Morning", "Afternoon", "Evening", YOU MUST INFER CONCRETE TIMES based on the user's preferences or defaults:
       - Morning: 10:00 AM
       - Afternoon: 2:00 PM
       - Evening: 6:00 PM
       
       Do NOT ask the user for times again if they said "schedule it". Just pick reasonable defaults and generate the JSON.
       
       Format:
       ```json
       {
         "action": "create_events",
         "events": [
           {
             "summary": "Python Basics",
             "description": "Variables, Data Types",
             "start_iso": "2025-11-20T10:00:00+05:30",
             "end_iso": "2025-11-20T11:30:00+05:30"
           },
           {
             "summary": "NumPy Intro",
             "description": "Basic arrays",
             "start_iso": "2025-11-20T12:00:00+05:30",
             "end_iso": "2025-11-20T13:00:00+05:30"
           }
         ]
       }
       ```

4) You DO NOT directly call Python functions. They are already called outside and results are put in [CONTEXT]. 
   EXCEPTION: For updating events or batch creating events, you use the JSON format above.
"""


def chat_with_agent(user_message: str, history: list[dict], context: dict | None = None) -> str:
    """
    Send a message to Gemini with history and extra context.
    """
    parts = []

    # System prompt
    parts.append({"text": SYSTEM_PROMPT})

    # Add context (like today's date, calendar results, etc.)
    if context:
        parts.append({"text": f"[SYSTEM CONTEXT]\n{context}"})

    # Add History
    # We'll format history as a transcript for the model to see previous turns
    history_text = ""
    for turn in history:
        role = turn["role"]
        content = turn["content"]
        history_text += f"[{role.upper()}]: {content}\n"
    
    if history_text:
        parts.append({"text": f"[CONVERSATION HISTORY]\n{history_text}"})

    # User message
    parts.append({"text": f"[USER]\n{user_message}"})

    try:
        resp = model.generate_content(
            contents=[{"role": "user", "parts": parts}],
        )

        # Extract text
        if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
            text = resp.candidates[0].content.parts[0].text
            if text is not None:
                return text.strip()
    except Exception as e:
        return f"(Error calling Gemini: {e})"

    return "(No response from model)"


# ========================
# FLASK WEB SERVER
# ========================

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

import uuid

# Global sessions storage
# Structure: { session_id: { 'title': str, 'history': list, 'created_at': datetime } }
sessions = {}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/sessions", methods=["GET"])
def get_sessions():
    # Return list of sessions sorted by creation time (newest first)
    # For simplicity, we just return them as is or sorted if we added timestamps
    # Let's just return a list of {id, title}
    session_list = [
        {"id": sid, "title": s["title"]} 
        for sid, s in sessions.items()
    ]
    # Reverse to show newest first (assuming insertion order is preserved in recent python)
    return jsonify(session_list[::-1])

@app.route("/new_chat", methods=["POST"])
def new_chat():
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "title": "New Chat",
        "history": []
    }
    return jsonify({"id": session_id, "title": "New Chat"})

@app.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    if session_id in sessions:
        del sessions[session_id]
        return jsonify({"success": True})
    return jsonify({"error": "Session not found"}), 404

@app.route("/history/<session_id>", methods=["GET"])
def get_history(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(sessions[session_id]["history"])

@app.route("/chat", methods=["POST"])
def chat_endpoint():
    data = request.json
    user_msg = data.get("message", "")
    session_id = data.get("session_id")
    
    if not user_msg:
        return jsonify({"error": "No message provided"}), 400

    # Create new session if not provided or invalid
    if not session_id or session_id not in sessions:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "title": "New Chat",
            "history": []
        }
    
    session = sessions[session_id]
    chat_history = session["history"]

    # Update title if it's the first message
    if len(chat_history) == 0:
        # Simple title generation: first 30 chars of message
        session["title"] = user_msg[:30] + "..." if len(user_msg) > 30 else user_msg

    # 1. Context & Intent Detection
    today_info = get_current_datetime()
    context = {"today_info": today_info}
    events_updated = False
    
    lower_msg = user_msg.lower()
    is_reschedule = "reschedule" in lower_msg or "move" in lower_msg or "change" in lower_msg
    
    # 2. Auto-create logic (Tomorrow at X)
    # Skip if reschedule to avoid duplicates
    if not is_reschedule and "tomorrow" in lower_msg and ("am" in lower_msg or "pm" in lower_msg):
        auto_info = auto_create_tomorrow_event(user_msg, today_info)
        if auto_info:
            context["auto_event_info"] = {
                "summary": auto_info["summary"],
                "start_iso": auto_info["start_dt"].isoformat(),
                "end_iso": auto_info["end_dt"].isoformat(),
                "calendar_result": auto_info["calendar_result"],
            }
            events_updated = True

    # Define now for search
    tz = get_ist_tz()
    now = dt.datetime.now(tz)
    
    # 3. Call Gemini Agent
    # We need to pass the history and context
    agent_response = chat_with_agent(user_msg, chat_history, context)
    
    # Update history
    chat_history.append({"role": "user", "content": user_msg})
    chat_history.append({"role": "model", "content": agent_response})
    
    return jsonify({
        "response": agent_response,
        "events_updated": events_updated,
        "session_id": session_id,
        "title": session["title"]
    })

@app.route("/events")
def events_endpoint():
    tz = get_ist_tz()
    now = dt.datetime.now(tz)
    start_search = now.isoformat()
    end_search = (now + dt.timedelta(days=7)).isoformat()
    
    list_res = list_calendar_events(start_search, end_search)
    return jsonify(list_res)

if __name__ == "__main__":
    print("🚀 Starting StudyCopilot Web Server on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
