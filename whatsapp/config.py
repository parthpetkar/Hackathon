import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

class Config:
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
    BACKEND_URL = os.getenv("BACKEND_URL")

config = Config()