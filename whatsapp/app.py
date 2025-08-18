# whatsapp-app/app.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
from config import Config
import os
import logging
import httpx

load_dotenv()  # Load .env

app = FastAPI()
logger = logging.getLogger("whatsapp_app")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# Config from env
TWILIO_ACCOUNT_SID = Config.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = Config.TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_NUMBER = Config.TWILIO_WHATSAPP_NUMBER
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/response")  # Ngrok or prod URL

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    try:
        form_data = await request.form()
        print(form_data)
        from_number = form_data.get("From")  # e.g., whatsapp:+1234567890
        body = form_data.get("Body")  # User's query
        if not body:
            raise HTTPException(status_code=400, detail="No message body")

        # Session ID (use From as proxy for Call SID)
        call_sid = from_number.replace("whatsapp:", "wa_")

        # Forward to backend /response
        payload = {
            "query": body,
            "call_sid": call_sid,
            # Add lat/lon/region if extracted (e.g., via regex or LLM in this app)
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(BACKEND_URL, json=payload)
            if resp.status_code != 200:
                logger.error(f"Backend error: {resp.text}")
                output = "Sorry, the service is unavailable. Try again later."
            else:
                result = resp.json()
                output = result.get("output", "No response generated.")

        # Create TwiML response
        twiml = MessagingResponse()
        twiml.message(output)

        return Response(content=str(twiml), media_type="application/xml")
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        twiml = MessagingResponse()
        twiml.message("An error occurred. Please try again.")
        return Response(content=str(twiml), media_type="application/xml")