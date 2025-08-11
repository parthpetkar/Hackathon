from dotenv import load_dotenv
from twilio.rest import Client
import os
load_dotenv()
client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

call = client.calls.create(
    url=os.getenv("TWILIO_VOICE_URL"),
    to="+919373063894",
    from_=os.getenv("TWILIO_NUMBER")
)
print(call.sid)
