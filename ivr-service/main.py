from dotenv import load_dotenv
load_dotenv()
import os

from app import app

if __name__ == "__main__":
    # Validate required environment variables
    REQUIRED_ENVS = [
        "TWILIO_ACCOUNT_SID", 
        "TWILIO_AUTH_TOKEN", 
        "TWILIO_NUMBER", 
        "GROQ_API_KEY"
    ]
    missing_envs = [env for env in REQUIRED_ENVS if not os.getenv(env)]
    if missing_envs:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_envs)}")
    
    app.run(port=5050, debug=True)