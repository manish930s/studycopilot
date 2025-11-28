import os
import datetime as dt
from zoneinfo import ZoneInfo
import requests
import re
import google.generativeai as genai
from google.generativeai import types as genai_types
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import pypdf
import calendar_bridge

load_dotenv()

# ========================
# CONFIGURATION
# ========================

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("Please set the GOOGLE_API_KEY environment variable first.")

genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-2.0-flash"
model = genai.GenerativeModel(MODEL_NAME)

# URL of your local Flask bridge (no Cloudflare)
CALENDAR_BRIDGE_URL = "http://127.0.0.1:5001/create_event"

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'md'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ========================
# RAG & TEXT PROCESSING
# ========================

class SimpleRAG:
    def __init__(self):
        self.documents = {}  # filename -> text content

    def add_document(self, filename, text):
        self.documents[filename] = text

    def retrieve_context(self, query):
        # Check if query is a filename in our documents
        if query in self.documents:
            # Return the full document content for quiz generation
            return self.documents[query]
        
        # Otherwise, do keyword matching for RAG search
        relevant_chunks = []
        query_lower = query.lower()
        
        for filename, text in self.documents.items():
            # Split into rough chunks (paragraphs)
            paragraphs = text.split('\n\n')
            for p in paragraphs:
                if any(word in p.lower() for word in query_lower.split() if len(word) > 4):
                    relevant_chunks.append(f"[Source: {filename}]\n{p.strip()}")
        
        # Return top 3 chunks
        return "\n\n".join(relevant_chunks[:3]) if relevant_chunks else None


rag_system = SimpleRAG()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(filepath):
    ext = filepath.rsplit('.', 1)[1].lower()
    text = ""
    try:
        if ext == 'pdf':
            reader = pypdf.PdfReader(filepath)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        else:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
    return text

# ========================
# Timezone helpers
# ========================

def get_ist_tz() -> dt.tzinfo:
    """
    Safely get Asia/Kolkata timezone.
    """
    try:
        return ZoneInfo("Asia/Kolkata")
    except Exception:
        return dt.timezone(dt.timedelta(hours=5, minutes=30))


# ========================
# Tools
# ========================

def get_current_datetime(timezone: str = "Asia/Kolkata") -> dict:
    """
    Returns current date/time.
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


def create_calendar_event(summary: str, description: str, start_iso: str, end_iso: str, access_token: str = None) -> dict:
    """
    Call local calendar_bridge module to create an event.
    """
    try:
        return calendar_bridge.add_study_block(summary, description, start_iso, end_iso, access_token)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_calendar_events(time_min: str, time_max: str, max_results: int = 10, access_token: str = None) -> dict:
    """
    Call local calendar_bridge module to list events.
    """
    try:
        return calendar_bridge.list_events(time_min, time_max, max_results, access_token)
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ========================

def update_calendar_event(event_id: str, summary: str = None, description: str = None, start_iso: str = None, end_iso: str = None, access_token: str = None) -> dict:
    """
    Call local calendar_bridge module to update an event.
    """
    try:
        return calendar_bridge.update_event(event_id, summary, description, start_iso, end_iso, access_token)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def delete_calendar_event(event_id: str, access_token: str = None) -> dict:
    """
    Call local calendar_bridge module to delete an event.
    """
    try:
        return calendar_bridge.delete_event(event_id, access_token)
    except Exception as e:
        return {"ok": False, "error": str(e)}

def auto_create_tomorrow_event(user_message: str, today_info: dict, access_token: str = None) -> dict | None:
    """
    Very simple 'direct save' helper.
    """
    text = user_message.lower()

    if "tomorrow" not in text:
        return None

    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text)
    if not m:
        return None

    hour = int(m.group(1))
    minute = int(m.group(2) or "0")
    ampm = m.group(3)

    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0

    today_date = dt.datetime.fromisoformat(today_info["date"] + "T00:00:00")
    ist = get_ist_tz()
    today_date = today_date.replace(tzinfo=ist)

    start_dt = today_date + dt.timedelta(days=1, hours=hour, minutes=minute)
    end_dt = start_dt + dt.timedelta(minutes=30)

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
        access_token=access_token
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

SYSTEM_PROMPT = """
You are a personal Study & Career Co-Pilot.

Capabilities:
- Help plan study, AI/ML learning, Kaggle competitions, MCA exam prep.
- You know how to reason about today's date and relative dates using the `get_current_datetime` tool.
- You can create Google Calendar events via the `create_calendar_event` tool.
- You can LIST events using `list_calendar_events` and UPDATE them using `update_calendar_event`.
- You have access to uploaded documents (Context-Aware RAG). If [RAG CONTEXT] is provided, use it to answer the user's questions.

Persona:
- You are a friendly, encouraging, and supportive mentor.
- You care about the user's progress and well-being.
- Your tone should be positive, motivating, and professional yet accessible.

Personalization:
- You have access to the user's name in [SYSTEM CONTEXT] under 'user_name'.
- Always address the user by their name occasionally (e.g., "Hello Manish", "Great job, Manish!", "Don't worry, Manish").
- Make the user feel seen and supported.

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
   
   (C) Rescheduling / Updating (CRITICAL) - "The Reshuffle Protocol":
       If the user says "I missed yesterday's session" or wants to reschedule:
       1. Check the [SYSTEM CONTEXT] for 'past_events' or 'upcoming_events'.
       2. Identify the missed or relevant event.
       3. Propose a new time based on the user's schedule (or ask for one).
       4. Once you have the ID and the new time, output the JSON block to update it.
       
       IMPORTANT: 'eventId' must be the actual Google Calendar ID string found in [SYSTEM CONTEXT].
       
       CRITICAL: IF YOU CANNOT FIND THE EVENT IN [SYSTEM CONTEXT], DO NOT HALLUCINATE AN ID.
       Instead, tell the user: "I couldn't find that event in your current calendar. Please check if you are logged into the correct account or if the event exists."
       
       Format:
       ```json
       {
         "action": "update_event",
         "eventId": "EVENT_ID_FROM_CONTEXT",
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
           }
         ]
       }
       ```

   (E) Deletion:
       If the user asks to delete an event or multiple events:
       1. Look at [SYSTEM CONTEXT] -> 'upcoming_events' (or 'past_events') to find the event(s) matching the user's description.
       2. Use the 'id' from those events as the 'eventId'.
       3. If deleting a single event, use "delete_event" with "eventId".
       4. If deleting multiple events, use "delete_events" with "eventIds" (list of strings).
       
       Format (Single):
       ```json
       {
         "action": "delete_event",
         "eventId": "EVENT_ID_HERE"
       }
       ```

       Format (Multiple):
       ```json
       {
         "action": "delete_events",
         "eventIds": ["ID_1", "ID_2", "ID_3"]
       }
       ```

4) You DO NOT directly call Python functions. They are already called outside and results are put in [CONTEXT]. 
   EXCEPTION: For updating, creating, or deleting events, you use the JSON format above.
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
        context_str = f"[SYSTEM CONTEXT]\n{context}"
        # Add RAG context if available
        if context.get("rag_context"):
            context_str += f"\n\n[RAG CONTEXT]\n{context['rag_context']}"
            
        parts.append({"text": context_str})

    # Add History
    history_text = ""
    for turn in history:
        role = turn["role"]
        content = turn["content"]
        history_text += f"[{role.upper()}]: {content}\n"
    
    if history_text:
        parts.append({"text": f"[CONVERSATION HISTORY]\n{history_text}"})

    # User message
    parts.append({"text": f"[USER]\n{user_message}"})

    content = {
        "role": "user",
        "parts": parts
    }

    try:
        resp = model.generate_content(
            contents=[content],
        )

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

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import uuid
import json

# Explicitly set template and static folders for PythonAnywhere
template_dir = os.path.abspath('/home/manish2111/mysite/templates')
static_dir = os.path.abspath('/home/manish2111/mysite/static')
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "STUDY_COPILOT_SECURE_SECRET_KEY_123") # Load from env or fallback
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global sessions storage
sessions = {}

# Load existing files into RAG system on startup
def load_existing_files():
    """Load all existing files from uploads folder (recursive) into RAG system"""
    if os.path.exists(UPLOAD_FOLDER):
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for filename in files:
                if allowed_file(filename):
                    filepath = os.path.join(root, filename)
                    print(f"Loading {filename} into RAG system...")
                    text = extract_text_from_file(filepath)
                    if text:
                        # Use filename as key (assuming unique names per user, or global uniqueness not strictly enforced for RAG yet)
                        rag_system.add_document(filename, text)
                        print(f"✓ Loaded {filename} ({len(text)} chars)")
                    else:
                        print(f"✗ Failed to extract text from {filename}")

# Load files on startup
load_existing_files()

@app.route("/upload", methods=["POST"])
def upload_endpoint():
    """Handle file uploads"""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Extract text and add to RAG system
        text = extract_text_from_file(filepath)
        if text:
            rag_system.add_document(filename, text)
            return jsonify({"success": True, "filename": filename})
        else:
            return jsonify({"success": False, "error": "Failed to extract text"}), 500
    
    return jsonify({"success": False, "error": "Invalid file type"}), 400


@app.route("/")
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template("index.html", user_name=session.get('user_name'))

@app.route("/login")
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template("login.html")

@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.json
    # In a real app, verify the Firebase token here using firebase-admin SDK
    # For now, we trust the client-side authentication for this demo
    session['user_id'] = data.get('uid')
    session['user_email'] = data.get('email')
    session['user_name'] = data.get('name')
    session['access_token'] = data.get('access_token') # Store Google OAuth Access Token
    print(f"[DEBUG] /auth/login: Stored access_token ending in ...{session['access_token'][-6:] if session.get('access_token') else 'None'}")
    return jsonify({"success": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/sessions", methods=["GET"])
def get_sessions():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify([])
        
    session_list = [
        {"id": sid, "title": s["title"]} 
        for sid, s in sessions.items()
        if s.get("user_id") == user_id
    ]
    return jsonify(session_list[::-1])

@app.route("/new_chat", methods=["POST"])
def new_chat():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "title": "New Chat",
        "history": [],
        "user_id": user_id
    }
    return jsonify({"id": session_id, "title": "New Chat"})

@app.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    user_id = session.get('user_id')
    if session_id in sessions:
        # Check ownership
        if sessions[session_id].get("user_id") == user_id:
            del sessions[session_id]
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Unauthorized"}), 403
    return jsonify({"error": "Session not found"}), 404

@app.route("/history/<session_id>", methods=["GET"])
def get_history(session_id):
    user_id = session.get('user_id')
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404
        
    # Check ownership
    if sessions[session_id].get("user_id") != user_id:
        return jsonify({"error": "Unauthorized"}), 403
        
    return jsonify(sessions[session_id]["history"])

@app.route("/upload", methods=["POST"])
def upload_file():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        # Create user-specific folder
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)
            
        filepath = os.path.join(user_folder, filename)
        file.save(filepath)
        
        # Extract and index text immediately
        text = extract_text_from_file(filepath)
        rag_system.add_document(filename, text)
        
        return jsonify({"success": True, "filename": filename, "message": "File uploaded and indexed."})
    
    return jsonify({"error": "File type not allowed"}), 400

@app.route("/chat", methods=["POST"])
def chat_endpoint():
    data = request.json
    user_msg = data.get("message", "")
    session_id = data.get("session_id")
    
    if not user_msg:
        return jsonify({"error": "No message provided"}), 400

    if not session_id or session_id not in sessions:
        user_id = session.get('user_id')
        if not user_id:
             return jsonify({"error": "Unauthorized"}), 401
             
        session_id = str(uuid.uuid4())
        sessions[session_id] = {
            "title": "New Chat",
            "history": [],
            "user_id": user_id
        }
    
    session_data = sessions[session_id]
    chat_history = session_data["history"]

    if len(chat_history) == 0:
        session_data["title"] = user_msg[:30] + "..." if len(user_msg) > 30 else user_msg

    # 1. Context & Intent Detection
    today_info = get_current_datetime()
    user_name = session.get('user_name', 'User')
    context = {
        "today_info": today_info,
        "user_name": user_name
    }
    events_updated = False
    
    lower_msg = user_msg.lower()
    # Expanded keywords to include deletion/cancellation
    is_calendar_action = any(k in lower_msg for k in ["reschedule", "move", "change", "missed", "delete", "remove", "cancel"])
    
    # 2. Handle calendar requests - fetch upcoming events to help agent
    # CRITICAL: Always get the fresh token from the session for the CURRENT user
    access_token = session.get('access_token')
    print(f"[DEBUG] /chat: Using access_token ending in ...{access_token[-6:] if access_token else 'None'}")
    
    if is_calendar_action:
        tz = get_ist_tz()
        now = dt.datetime.now(tz)
        # Look back 2 days for "missed" events, look forward 30 days for upcoming
        start_search = (now - dt.timedelta(days=2)).isoformat()
        end_search = (now + dt.timedelta(days=30)).isoformat()
        list_res = list_calendar_events(start_search, end_search, max_results=50, access_token=access_token)
        
        if list_res.get("ok") and list_res.get("events"):
            context["upcoming_events"] = list_res["events"]
            # Also specifically flag past events if user said "missed"
            if "missed" in lower_msg:
                past_events = [e for e in list_res["events"] if e.get("start", {}).get("dateTime") < now.isoformat()]
                context["past_events"] = past_events
    
    # 3. RAG Context Retrieval
    rag_context = rag_system.retrieve_context(user_msg)
    if rag_context:
        context["rag_context"] = rag_context

    # 4. Auto-create logic (Tomorrow at X)
    if not is_calendar_action and "tomorrow" in lower_msg and ("am" in lower_msg or "pm" in lower_msg):
        auto_info = auto_create_tomorrow_event(user_msg, today_info, access_token=access_token)
        if auto_info:
            context["auto_event_info"] = {
                "summary": auto_info["summary"],
                "start_iso": auto_info["start_dt"].isoformat(),
                "end_iso": auto_info["end_dt"].isoformat(),
                "calendar_result": auto_info["calendar_result"],
            }
            events_updated = True

    # 5. Call Gemini Agent
    agent_response = chat_with_agent(user_msg, chat_history, context)
    
    # 6. Parse JSON from agent response
    json_match = re.search(r'```json(.*?)```', agent_response, re.DOTALL)
    if json_match:
        try:
            json_data = json.loads(json_match.group(1))
            action = json_data.get("action")
            
            if action == "create_events":
                events = json_data.get("events", [])
                created_count = 0
                failed_count = 0
                
                for event in events:
                    result = create_calendar_event(
                        summary=event.get("summary", "Event"),
                        description=event.get("description", ""),
                        start_iso=event.get("start_iso"),
                        end_iso=event.get("end_iso"),
                        access_token=access_token
                    )
                    
                    if result.get("ok"):
                        created_count += 1
                    else:
                        failed_count += 1
                        print(f"[ERROR] Failed to create event '{event.get('summary')}': {result.get('error')}")
                
                if created_count > 0:
                    events_updated = True
                    confirmation = f"\n\n✅ Successfully created {created_count} event(s) in your Google Calendar!"
                    if failed_count > 0:
                        confirmation += f" ({failed_count} failed)"
                    agent_response += confirmation
            
            elif action == "update_event":
                event_id = json_data.get("eventId")
                start_iso = json_data.get("start_iso")
                end_iso = json_data.get("end_iso")
                
                if event_id and start_iso and end_iso:
                    result = update_calendar_event(
                        event_id=event_id,
                        start_iso=start_iso,
                        end_iso=end_iso,
                        access_token=access_token
                    )
                    
                    if result.get("ok"):
                        events_updated = True
                        agent_response += "\n\n✅ Event updated successfully!"
                    else:
                        agent_response += f"\n\n❌ Failed to update event: {result.get('error')}"
            
            elif action == "delete_event":
                event_id = json_data.get("eventId")
                if event_id:
                    result = delete_calendar_event(event_id, access_token=access_token)
                    if result.get("ok"):
                        events_updated = True
                        agent_response += "\n\n✅ Event deleted successfully!"
                    else:
                        agent_response += f"\n\n❌ Failed to delete event: {result.get('error')}"

            elif action == "delete_events":
                event_ids = json_data.get("eventIds", [])
                deleted_count = 0
                failed_count = 0
                
                for event_id in event_ids:
                    result = delete_calendar_event(event_id, access_token=access_token)
                    if result.get("ok"):
                        deleted_count += 1
                    else:
                        failed_count += 1
                
                if deleted_count > 0:
                    events_updated = True
                    msg = f"\n\n✅ Successfully deleted {deleted_count} event(s)."
                    if failed_count > 0:
                        msg += f" ({failed_count} failed)"
                    agent_response += msg
        
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON from agent response: {e}")
        except Exception as e:
            print(f"[ERROR] Error processing agent JSON: {e}")
    
    chat_history.append({"role": "user", "content": user_msg})
    chat_history.append({"role": "model", "content": agent_response})
    
    return jsonify({
        "response": agent_response,
        "events_updated": events_updated,
        "session_id": session_id,
        "title": session_data["title"]
    })

@app.route("/delete_event", methods=["POST"])
def delete_event_endpoint():
    data = request.json
    event_id = data.get("event_id")
    
    if not event_id:
        return jsonify({"error": "No event_id provided"}), 400
        
    access_token = session.get('access_token')
    result = delete_calendar_event(event_id, access_token=access_token)
    return jsonify(result)

@app.route("/generate_quiz", methods=["POST"])
def generate_quiz_endpoint():
    """
    Generate quiz questions based on mode (upload, recall, interview).
    """
    data = request.json
    mode = data.get("mode")  # "upload", "recall", or "interview"
    
    try:
        if mode == "upload":
            # Quiz My Uploads mode
            filename = data.get("filename")
            if not filename:
                return jsonify({"error": "No filename provided"}), 400
            
            # Use RAG to get context from the file
            context = rag_system.retrieve_context(filename)
            if not context:
                return jsonify({"error": "File not found or no content"}), 404
            
            # Generate quiz prompt
            quiz_prompt = f"""Based on the following document content, generate 5 multiple-choice questions to test understanding.

Document Content:
{context}

Generate questions in this EXACT JSON format:
```json
{{
    "questions": [
        {{
            "question": "Question text here?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct": 0
        }}
    ]
}}
```

Make the questions challenging but fair. The "correct" field should be the index (0-3) of the correct option."""

            response = model.generate_content(quiz_prompt)
            quiz_data = parse_json_from_response(response.text)
            
            if quiz_data:
                return jsonify(quiz_data)
            else:
                return jsonify({"error": "Failed to generate quiz"}), 500
                
        elif mode == "recall":
            # Daily Recall mode - get yesterday's events
            tz = get_ist_tz()
            yesterday = dt.datetime.now(tz) - dt.timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0).isoformat()
            end = yesterday.replace(hour=23, minute=59, second=59).isoformat()
            
            events_res = list_calendar_events(start, end)
            events = events_res.get("events", [])
            
            if not events:
                return jsonify({"error": "No study sessions found for yesterday"}), 404
            
            topics = [e.get("summary", "") for e in events]
            topics_str = ", ".join(topics)
            
            quiz_prompt = f"""You studied these topics yesterday: {topics_str}

Generate 5 quick recall questions to test retention. Use this EXACT JSON format:
```json
{{
    "questions": [
        {{
            "question": "Question text here?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct": 0
        }}
    ]
}}
```"""

            response = model.generate_content(quiz_prompt)
            quiz_data = parse_json_from_response(response.text)
            
            if quiz_data:
                quiz_data["topics"] = topics
                return jsonify(quiz_data)
            else:
                return jsonify({"error": "Failed to generate quiz"}), 500
                
        elif mode == "interview":
            # Mock Interview mode
            job_role = data.get("job_role", "Software Developer")
            
            interview_prompt = f"""You are conducting a mock interview for the role: {job_role}

Generate 3 technical/behavioral interview questions. Use this EXACT JSON format:
```json
{{
    "questions": [
        {{
            "question": "Interview question here?",
            "type": "open"
        }}
    ]
}}
```

Make questions realistic and relevant to the role."""

            response = model.generate_content(interview_prompt)
            quiz_data = parse_json_from_response(response.text)
            
            if quiz_data:
                return jsonify(quiz_data)
            else:
                return jsonify({"error": "Failed to generate interview questions"}), 500
        else:
            return jsonify({"error": "Invalid mode"}), 400
            
    except Exception as e:
        print(f"[ERROR] Quiz generation failed: {e}")
        return jsonify({"error": str(e)}), 500



@app.route("/evaluate_interview", methods=["POST"])
def evaluate_interview():
    """Evaluate mock interview answers"""
    data = request.json
    qa_pairs = data.get("qa_pairs", [])
    job_role = data.get("job_role", "Software Developer")
    
    if not qa_pairs:
        return jsonify({"error": "No answers provided"}), 400
        
    # Construct prompt
    qa_text = ""
    for i, item in enumerate(qa_pairs):
        qa_text += f"Q{i+1}: {item['question']}\nA: {item['answer']}\n\n"
        
    prompt = f"""You are an expert interviewer for the role of {job_role}.
Evaluate the following candidate's answers. Provide constructive feedback, highlighting strengths and areas for improvement.
Also provide a rating (1-10) for each answer.

Interview Transcript:
{qa_text}

Provide the evaluation in this EXACT JSON format:
```json
{{
    "overall_feedback": "General summary of performance...",
    "evaluations": [
        {{
            "question_index": 0,
            "rating": 8,
            "feedback": "Specific feedback for this answer..."
        }}
    ]
}}
```"""

    try:
        response = model.generate_content(prompt)
        eval_data = parse_json_from_response(response.text)
        
        if eval_data:
            return jsonify(eval_data)
        else:
            # Fallback if JSON parsing fails
            return jsonify({
                "overall_feedback": response.text,
                "evaluations": []
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def parse_json_from_response(text):
    """Extract JSON from markdown code blocks."""
    import re
    json_match = re.search(r'```json(.*?)```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            return None
    return None

@app.route("/list_uploads", methods=["GET"])
def list_uploads():
    """List all uploaded files for the current user"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"files": []})
        
    files = []
    user_folder = os.path.join(UPLOAD_FOLDER, user_id)
    
    if os.path.exists(user_folder):
        for filename in os.listdir(user_folder):
            filepath = os.path.join(user_folder, filename)
            if os.path.isfile(filepath):
                files.append({
                    "name": filename,
                    "size": os.path.getsize(filepath)
                })
    return jsonify({"files": files})

@app.route("/delete_file", methods=["POST"])
def delete_file():
    """Delete an uploaded file"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    filename = data.get("filename")
    
    if not filename:
        return jsonify({"error": "No filename provided"}), 400
        
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    filepath = os.path.join(user_folder, filename)
    
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            # Also remove from RAG system if possible (simple implementation: just reload or ignore)
            if filename in rag_system.documents:
                del rag_system.documents[filename]
            return jsonify({"success": True})
        else:
            return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================
# DASHBOARD & ANALYTICS
# ========================

QUIZ_HISTORY_FILE = "quiz_history.json"

def load_quiz_history():
    if os.path.exists(QUIZ_HISTORY_FILE):
        try:
            with open(QUIZ_HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_quiz_history(history):
    with open(QUIZ_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

@app.route("/dashboard_stats", methods=["GET"])
def dashboard_stats():
    """Aggregate stats for the dashboard"""
    
    # 1. Session Count
    session_count = len(sessions)
    
    # 2. File Count
    file_count = 0
    if os.path.exists(UPLOAD_FOLDER):
        file_count = len([f for f in os.listdir(UPLOAD_FOLDER) if allowed_file(f)])
        
    # 3. Upcoming Events (Next 7 days)
    upcoming_events = []
    try:
        tz = get_ist_tz()
        now = dt.datetime.now(tz)
        end_time = now + dt.timedelta(days=7)
        
        end_time = now + dt.timedelta(days=7)
        
        access_token = session.get('access_token') # Get token from session
        print(f"[DEBUG] /dashboard_stats: access_token ending in ...{access_token[-6:] if access_token else 'None'}")
        
        if not access_token:
            # If no token, return empty events rather than falling back to server token
            upcoming_events = []
        else:
            # Fetch events starting from the beginning of today so "today's" events show up even if past
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            list_res = list_calendar_events(
                today_start.isoformat(), 
                end_time.isoformat(), 
                max_results=5,
                access_token=access_token # Pass token to bridge
            )
            print(f"[DEBUG] /dashboard_stats: list_res keys: {list_res.keys()}")
            
            if list_res.get("ok"):
                upcoming_events = list_res.get("events", [])
    except Exception as e:
        print(f"Error fetching dashboard events: {e}")

    # 4. Knowledge Stats
    quiz_history = load_quiz_history()
    user_id = session.get('user_id')
    topic_stats = {}
    
    for entry in quiz_history:
        # Filter by user_id
        if entry.get("user_id") != user_id:
            continue
            
        topic = entry.get("topic", "General")
        score = entry.get("score", 0)
        total = entry.get("total", 1)
        percentage = (score / total) * 100
        
        if topic not in topic_stats:
            topic_stats[topic] = {"total_score": 0, "count": 0}
        
        topic_stats[topic]["total_score"] += percentage
        topic_stats[topic]["count"] += 1
        
    knowledge_profile = []
    for topic, data in topic_stats.items():
        avg_score = round(data["total_score"] / data["count"])
        knowledge_profile.append({"topic": topic, "level": avg_score})
        
    # Sort by level descending
    knowledge_profile.sort(key=lambda x: x["level"], reverse=True)

    return jsonify({
        "user_name": session.get('user_name', 'User'),
        "total_chats": session_count,
        "total_files": file_count,
        "upcoming_events": upcoming_events,
        "upcoming_events_count": len(upcoming_events),
        "knowledge_profile": knowledge_profile
    })

@app.route("/submit_quiz_result", methods=["POST"])
def submit_quiz_result():
    """Save quiz results to history"""
    data = request.json
    topic = data.get("topic", "General")
    score = data.get("score", 0)
    total = data.get("total", 0)
    
    if total == 0:
        return jsonify({"error": "Invalid total score"}), 400
        
    history = load_quiz_history()
    history.append({
        "date": dt.datetime.now().isoformat(),
        "user_id": session.get('user_id'), # Save user_id
        "topic": topic,
        "score": score,
        "total": total
    })
    save_quiz_history(history)
    
    return jsonify({"success": True})

@app.route("/events")
def events_endpoint():
    if 'access_token' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    tz = get_ist_tz()
    now = dt.datetime.now(tz)
    # Start search from the beginning of today (00:00:00)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_search = today_start.isoformat()
    end_search = (now + dt.timedelta(days=7)).isoformat()
    
    access_token = session.get('access_token')
    if not access_token:
        print("[DEBUG] /events: No access_token in session")
        return jsonify({"error": "Unauthorized"}), 401

    print(f"[DEBUG] /events: Fetching events for token ending in ...{access_token[-6:]}")
    list_res = list_calendar_events(start_search, end_search, access_token=access_token)
    print(f"[DEBUG] /events: Bridge response: {list_res}")
    
    if not list_res.get("ok"):
        error_msg = list_res.get("error", "")
        if "accessNotConfigured" in error_msg or "disabled" in error_msg:
            # Extract project ID if possible or just give generic link
            project_id = "21392727344" # From the logs
            link = f"https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project={project_id}"
            return jsonify({"error": f"Google Calendar API not enabled. <a href='{link}' target='_blank'>Click here to enable it</a>, then refresh."}), 403
            
    return jsonify(list_res)

@app.route("/mark_event_complete", methods=["POST"])
def mark_event_complete():
    data = request.json
    event_id = data.get("event_id")
    current_summary = data.get("summary", "")
    
    if not event_id:
        return jsonify({"error": "Event ID required"}), 400
        
    # Toggle completion status
    if current_summary.startswith("✅ "):
        new_summary = current_summary[2:] # Remove checkmark
    else:
        new_summary = "✅ " + current_summary
        
    # Update the event
    access_token = session.get('access_token')
    res = update_calendar_event(event_id, summary=new_summary, access_token=access_token)
    return jsonify(res)

@app.route("/delete_calendar_event", methods=["POST"])
def delete_calendar_event_endpoint():
    data = request.json
    event_id = data.get("event_id")
    
    if not event_id:
        return jsonify({"error": "Event ID required"}), 400
    
    # Delete the event using the existing delete_calendar_event function
    access_token = session.get('access_token')
    res = delete_calendar_event(event_id, access_token=access_token)
    return jsonify(res)

# Manual tasks storage (in-memory)
manual_tasks = []
task_id_counter = 1

@app.route("/manual_tasks", methods=["GET"])
def get_manual_tasks():
    user_id = session.get('user_id')
    user_tasks = [t for t in manual_tasks if t.get("user_id") == user_id]
    return jsonify(user_tasks)

@app.route("/manual_tasks", methods=["POST"])
def create_manual_task():
    global task_id_counter
    data = request.json
    task = {
        "id": task_id_counter,
        "user_id": session.get('user_id'), # Save user_id
        "text": data.get("text", ""),
        "completed": False
    }
    manual_tasks.append(task)
    task_id_counter += 1
    return jsonify(task)

@app.route("/manual_tasks/<int:task_id>/toggle", methods=["PUT"])
def toggle_manual_task(task_id):
    user_id = session.get('user_id')
    for task in manual_tasks:
        if task["id"] == task_id and task.get("user_id") == user_id:
            task["completed"] = not task["completed"]
            return jsonify(task)
    return jsonify({"error": "Task not found"}), 404

@app.route("/manual_tasks/<int:task_id>", methods=["DELETE"])
def delete_manual_task(task_id):
    global manual_tasks
    user_id = session.get('user_id')
    # Only delete if task belongs to user
    manual_tasks = [task for task in manual_tasks if not (task["id"] == task_id and task.get("user_id") == user_id)]
    return jsonify({"ok": True})

if __name__ == "__main__":
    print("🚀 Starting StudyCopilot Web Server on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)

