from dotenv import load_dotenv
from twilio.rest import Client
import os

# Load environment variables
load_dotenv()

# Read ngrok URL from file
try:
    with open("ngrok_url.txt", "r") as f:
        public_url = f.read().strip()
except FileNotFoundError:
    raise SystemExit("Error: ngrok_url.txt not found. Run run.py first to start ngrok and the server.")

print(f"Using ngrok URL: {public_url}")

# Make Twilio call
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
call = client.calls.create(
    url=f"{public_url}/voice",
    to="+919373063894",
    from_=os.getenv("TWILIO_NUMBER")
)
print(f"Call SID: {call.sid}")
