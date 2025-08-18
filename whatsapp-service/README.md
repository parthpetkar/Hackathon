# WhatsApp Integration App

A lightweight FastAPI app to integrate WhatsApp messaging with a backend agricultural advisory service via Twilio. Forwards user queries to the backend `/response` endpoint and replies with generated answers.

## Setup

1. **Install Dependencies**  
   ```bash
   pip install -r requirements.txt
   ```
   Requirements: `fastapi`, `uvicorn`, `twilio`, `python-dotenv`, `httpx`.

2. **Configure Environment**  
   Copy `.env.example` to `.env` and update with your credentials:
   ```bash
   cp .env.example .env
   ```
   Required vars:
   - `TWILIO_ACCOUNT_SID`: Twilio Account SID
   - `TWILIO_AUTH_TOKEN`: Twilio Auth Token
   - `TWILIO_WHATSAPP_NUMBER`: e.g., `whatsapp:+14155238886` (Sandbox number)
   - `BACKEND_URL`: Backend API endpoint (e.g., `https://abc123.ngrok.io/response`)
   - `LOG_LEVEL`: e.g., `INFO`

3. **Run the App**  
   ```bash
   uvicorn app:app --reload --port 8009
   ```
   Expose via ngrok for Twilio webhooks: `ngrok http 8009`. Update Twilio WhatsApp Sandbox webhook with ngrok URL + `/whatsapp`.

## Notes
- For development, use ngrok to expose the app.
- Ensure the backend API is running and accessible (e.g., via ngrok or a hosted URL).
- Configure Twilio WhatsApp Sandbox for testing: Send `join <sandbox-keyword>` to the sandbox number.