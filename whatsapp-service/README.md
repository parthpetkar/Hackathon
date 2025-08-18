# WhatsApp Integration Service — Local Setup and Twilio Wiring (Windows PowerShell/Linux)

This guide provides a comprehensive walkthrough for setting up the WhatsApp Integration Service locally, exposing it via ngrok for Twilio webhooks, and connecting it to a backend agricultural advisory API. The service receives WhatsApp messages, forwards queries to the backend's `/response` endpoint, and replies with generated answers.

## Prerequisites
- **Python 3.10+** installed and available in PATH.
- **Twilio Account** with WhatsApp Sandbox activated (trial works; get credentials from [Twilio Console](https://www.twilio.com/console)).
- **ngrok** installed and available in PATH (`ngrok version` to verify). Download from [ngrok.com](https://ngrok.com).
- **Backend API** running and accessible (e.g., at `http://localhost:5000/response` or via ngrok). See backend README for setup.
- **Git** for cloning the repository (optional).

## 1) Clone and Open the WhatsApp Service
```bash
git clone <repository-url>  # If using a repo
cd whatsapp-app
```
Folder: `whatsapp-app/`

## 2) Create and Activate a Virtual Environment
**Windows (PowerShell)**:
```powershell
python -m venv venv
# Allow scripts if prompted
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```
**Linux/macOS**:
```bash
python3 -m venv venv
source venv/bin/activate
```

## 3) Configure Environment Variables
Copy `.env.example` to `.env` and fill in required values:
```bash
cp .env.example .env
```
Edit `.env` with a text editor. The `.env.example` structure is:
```bash
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=
BACKEND_URL=  # main backend url
LOG_LEVEL=
```

Required values:
- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID (from Twilio Console).
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token.
- `TWILIO_WHATSAPP_NUMBER`: Sandbox number, e.g., `whatsapp:+14155238886`.
- `BACKEND_URL`: Backend API endpoint, e.g., `https://<ngrok-id>.ngrok.io/response` or `http://localhost:5000/response`.
- `LOG_LEVEL`: Logging level, e.g., `INFO` or `DEBUG`.

Example `.env`:
```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
BACKEND_URL=https://abc123.ngrok.io/response
LOG_LEVEL=DEBUG
```

## 4) Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
Requirements: `fastapi`, `uvicorn`, `twilio`, `python-dotenv`, `httpx`, `tenacity`.

## 5) Start the WhatsApp Service and Expose with ngrok
Run the FastAPI app:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8009
```
Expose it publicly:
```bash
ngrok http 8009
```
- Copy the ngrok HTTPS URL (e.g., `https://def456.ngrok.io`).
- Notes:
  - Ensure ngrok is on PATH; otherwise, download/run manually.
  - Ngrok's free tier is for development; use a hosted solution (e.g., Vercel) for production.

## 6) Configure Twilio WhatsApp Sandbox
1. In [Twilio Console](https://www.twilio.com/console) > Messaging > WhatsApp > Sandbox:
   - Set "WHEN A MESSAGE COMES IN" webhook to `https://<ngrok-id>.ngrok.io/whatsapp` to redirect messages to your WhatsApp service.
   - HTTP method: POST.
2. Join the sandbox: From WhatsApp, send `join <sandbox-keyword>` (keyword from Twilio Console) to the sandbox number (e.g., `whatsapp:+14155238886`).
3. Save the configuration.

## 7) Test the Service
- Ensure the backend API is running (e.g., `uvicorn app:app --port 5000` and exposed via ngrok if not local).
- Send a WhatsApp message (e.g., "weather for the next 5 days") to the sandbox number.
- The service:
  - Receives the message at `/whatsapp`.
  - Forwards the query to `BACKEND_URL` as JSON (e.g., `{"query": "weather for the next 5 days", "call_sid": "wa_+1234567890"}`).
  - Returns the backend's response via WhatsApp.

## 8) Endpoint
### POST /whatsapp
Handles incoming WhatsApp messages from Twilio and forwards to the backend.

**Request** (Twilio form data):
- `From`: Sender's WhatsApp number (e.g., `whatsapp:+1234567890`).
- `Body`: User's query text.

**Payload to Backend** (POST to `BACKEND_URL`):
```json
{
    "query": "<user message>",
    "call_sid": "wa_<sender_number>"
}
```

**Response** (TwiML):
- XML with the backend's answer or an error message (e.g., "Service unavailable").

## Troubleshooting
- **Backend not receiving requests**:
  - Verify `BACKEND_URL` in `.env` matches the backend's ngrok URL or local address.
  - Test: `curl -X POST -H "Content-Type: application/json" -d '{"query":"test","call_sid":"test123"}' <BACKEND_URL>`.
  - Check backend logs for incoming POSTs to `/response`.
- **Webhook not triggered**:
  - Confirm ngrok is running (`http://localhost:4040` for dashboard).
  - Ensure Twilio webhook URL is correct (`https://<ngrok-id>.ngrok.io/whatsapp`).
- **Invalid JSON**:
  - Logs show double-quoted JSON payload (via `json.dumps`).
  - Ensure backend's `QueryRequest` model accepts the payload format.
- **Twilio errors**:
  - Verify `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_WHATSAPP_NUMBER`.
  - Check Twilio Console > Messaging > Logs for errors.
- **Logs**: Set `LOG_LEVEL=DEBUG` in `.env` and check logs for detailed errors (e.g., `Backend network error`).

## Project Structure
- App entry: `app.py` (FastAPI on port 8009).
- Config: `config.py` (loads `.env`).
- Webhook: `/whatsapp` (POST).

## Notes
- **Development**: Use ngrok for testing. For production, deploy to a platform like Vercel and update the Twilio webhook to a static URL.
- **Backend Dependency**: The service requires the backend API at `BACKEND_URL` (typically `http://localhost:5000/response` or a hosted/ngrok URL).
- **Security**: Add API key auth to the backend's `/response` endpoint and include in `httpx` headers for production.
- **Media Support**: Extend `app.py` to handle media (e.g., `MediaUrl0` from form data) if users send images/PDFs.