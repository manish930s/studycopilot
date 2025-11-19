# StudyCopilot - AI-Powered Study & Career Assistant 🎓

An intelligent study companion that integrates with Google Calendar to help manage your learning schedule, track tasks, and organize study sessions. Built with Flask, Google Gemini AI, and Google Calendar API.

---

## 📋 Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Technologies Used](#technologies-used)

---

## ✨ Features

### 🤖 AI-Powered Chat Assistant
- Conversational AI using **Google Gemini 2.0 Flash** model
- Context-aware responses for study planning and career guidance
- Multi-session chat support with history tracking
- Intelligent date/time parsing for natural language inputs

### 📅 Google Calendar Integration
- Create, update, and list calendar events
- Auto-schedule study blocks and reminders
- Support for relative dates ("tomorrow", "next Monday", etc.)
- Batch event creation for study plans
- Reschedule and manage existing events

### 💬 Interactive Web UI
- Modern, responsive chat interface
- Sidebar navigation with recent chats
- Real-time event updates display
- Session management (create, switch, delete chats)
- Tasks dashboard showing upcoming events

### 🎯 Smart Features
- Auto-detection of "tomorrow at X time" patterns
- Intelligent event title generation
- IST (Asia/Kolkata) timezone support
- Study plan generation and scheduling
- Exam prep and task reminders

---

## 📁 Project Structure

```
capston/
├── agent_app.py              # Main Flask web server with AI agent
├── calendar_bridge.py        # Google Calendar API bridge server
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (API keys)
├── token.json               # Google OAuth token (auto-generated)
├── client_secret_*.json     # Google OAuth credentials
├── static/
│   ├── script.js            # Frontend JavaScript logic
│   └── style.css            # UI styling
└── templates/
    └── index.html           # Main web interface
```

---

## 🔧 Prerequisites

1. **Python 3.10+** installed
2. **pip** package manager
3. **Google Account** with Calendar enabled
4. **Google Cloud Project** with:
   - Google Calendar API enabled
   - OAuth 2.0 Client ID (Desktop app) created
   - Client secret JSON downloaded

---

## 📦 Installation

### 1. Clone or Download the Project

```bash
cd c:\Users\Manish\Downloads\capston
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install flask python-dotenv google-generativeai google-api-python-client google-auth-httplib2 google-auth-oauthlib requests
```

Or use the requirements file (after updating it):

```bash
pip install -r requirements.txt
```

---

## ⚙️ Configuration

### 1. Set Up Google Calendar API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable **Google Calendar API**
4. Create **OAuth 2.0 Client ID** (Desktop application)
5. Download the client secret JSON file
6. Rename it and update `CLIENT_SECRET_FILE` in `calendar_bridge.py` (line 19-21)

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

Get your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

### 3. First-Time OAuth Setup

On first run, the calendar bridge will open a browser window for Google OAuth authentication. Sign in and grant calendar permissions. This creates `token.json` for future use.

---

## 🚀 Usage

### Starting the Application

You need to run **TWO servers** in separate terminals:

#### Terminal 1: Calendar Bridge (Port 5001)

```bash
python calendar_bridge.py
```

Expected output:
```
🚀 Serving Flask app on http://127.0.0.1:5001
```

#### Terminal 2: Main Agent App (Port 5000)

```bash
python agent_app.py
```

Expected output:
```
🚀 Starting StudyCopilot Web Server on http://127.0.0.1:5000
```

### Accessing the Web Interface

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

### Example Interactions

**Create a reminder:**
```
"Remind me to study DSA tomorrow at 11pm"
```

**Schedule a study plan:**
```
"Create a 3-day Python learning plan"
"Schedule this plan"
```

**List upcoming events:**
```
"What's on my calendar this week?"
```

**Reschedule an event:**
```
"Move my DSA study session to 3pm tomorrow"
```

---

## 🔌 API Endpoints

### Agent App (Port 5000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main web interface |
| `/chat` | POST | Send message to AI agent |
| `/sessions` | GET | List all chat sessions |
| `/new_chat` | POST | Create new chat session |
| `/sessions/<id>` | DELETE | Delete a chat session |
| `/history/<id>` | GET | Get chat history for session |
| `/events` | GET | Get upcoming calendar events |

### Calendar Bridge (Port 5001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/create_event` | POST | Create calendar event |
| `/list_events` | GET | List events in time range |
| `/update_event` | POST | Update existing event |

---

## 🛠️ Technologies Used

### Backend
- **Flask** - Web framework
- **Google Gemini AI** - Conversational AI model
- **Google Calendar API** - Calendar integration
- **Python 3.10+** - Core language

### Frontend
- **HTML5/CSS3** - Structure and styling
- **JavaScript (Vanilla)** - Interactive UI logic
- **Fetch API** - HTTP requests

### Authentication
- **OAuth 2.0** - Google Calendar authentication
- **Google Auth Libraries** - Token management

---

## 📝 Notes

- The application uses **IST (Asia/Kolkata)** timezone by default
- Chat sessions are stored in memory (will reset on server restart)
- Multiple instances of `agent_app.py` running may cause port conflicts
- Ensure both servers are running for full functionality

---

## 🐛 Troubleshooting

**Port already in use:**
```bash
# Kill existing Python processes or change port in code
```

**Calendar API errors:**
- Check if `token.json` exists and is valid
- Verify Google Calendar API is enabled in Cloud Console
- Ensure OAuth credentials file path is correct

**Gemini API errors:**
- Verify `GOOGLE_API_KEY` in `.env` file
- Check API quota limits in Google AI Studio



## 📄 License

This project is for educational purposes.

