## IVR Service — Local setup and Twilio wiring (Windows PowerShell)

This guide walks you end‑to‑end through running the IVR locally, exposing it via ngrok, wiring Twilio to your local server, and optionally triggering a test call.

### Prerequisites
- Python 3.10+ installed and available in PATH
- A Twilio account with a phone number (trial works if you verify your personal number)
- ngrok installed and available in PATH
  - Verify by running `ngrok version`
- The backend service running at <http://localhost:5000> (needed for actual answers)

### 1) Clone and open the IVR service
- Folder: `ivr-service`

### 2) Create and activate a virtual environment
```powershell
cd ivr-service
python -m venv venv
# If activation is blocked, allow scripts for this session only:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### 3) Configure environment variables
Create a `.env` file in `ivr-service/` using the template below (or copy `.env.example` and fill values).

Required:
- TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_NUMBER
- GROQ_API_KEY (used by backend processing)

Optional:
- ELEVENLABS_API_KEY (enables higher‑quality TTS)

Example `.env`:

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_NUMBER=+1xxxxxxxxxx
GROQ_API_KEY=your_groq_api_key
# Optional
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

### 4) Install dependencies
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 5) Start the IVR locally and expose it with ngrok
This script will start ngrok on port 5050, write the public URL to `ngrok_url.txt`, and then run the Flask app.

```powershell
python .\run.py
```

Notes:
- Ensure ngrok is installed and on PATH; otherwise `run.py` won’t be able to fetch the tunnel.
- The script prefers the HTTPS URL; Twilio requires a publicly accessible URL (HTTPS recommended).

### 6) Point your Twilio number to your local IVR
In Twilio Console:
1. Phone Numbers → Active numbers → click your number
2. Under Voice configuration (A Call Comes In):
   - Webhook: paste your ngrok HTTPS URL with `/voice` appended, e.g.
     `https://<your-ngrok-id>.ngrok.io/voice`
   - HTTP method: POST
3. Save

### 7) (Optional) Trigger a test outbound call from your machine
In a separate terminal (keep the IVR running):
```powershell
cd ivr-service
.\venv\Scripts\Activate.ps1
python .\make_call.py
```

What it does:
- Reads `ngrok_url.txt`
- Tells Twilio to call your number and fetch call instructions from `https://<ngrok>/voice`

Tip: In `make_call.py`, update the `to="+1xxxxxxxxxx"` number to your phone if needed. On Twilio trial, the callee must be a verified number.

### 8) Speak your query
- You’ll receive a call from your Twilio number.
- Select a language via keypad (DTMF), then speak your query after the beep and press `#`.
- The service processes your query via the backend and replies with a spoken answer.

### Troubleshooting
- Missing env vars: The app will exit and list any missing ones at startup.
- ngrok URL not found: Make sure `run.py` is running; it creates `ngrok_url.txt`.
- Backend dependency: The IVR expects a backend at `http://localhost:5000/response`. Start the backend before testing dynamic answers.
- Twilio trial: Calls/SMS are limited to verified numbers, and prompts may mention trial status.

### Useful paths
- IVR entrypoint: `main.py` (Flask app on port 5050)
- Local tunnel starter: `run.py` (starts ngrok and then Flask)
- Inbound webhook: `/voice` (POST)
- Test caller: `make_call.py`

That’s it. With the webhook set to `POST https://<ngrok>/voice`, your Twilio number will reach your local IVR.
