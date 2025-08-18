# Agri Assistant — Voice IVR + RAG Backend + WhatsApp

This repository contains a voice-first agriculture assistant.

Components:

- An IVR service that answers farmer queries over a phone call using multi-language TTS/DTMF
- A FastAPI backend that performs retrieval-augmented generation (RAG), external data fetches, and PDF ingestion
- A WhatsApp service (optional) for text-based interactions

## Architecture

![SystemArch](https://github.com/user-attachments/assets/7a710ace-5011-4cec-bcad-77fa0420f15e)

## Quick start map

1. Backend
	- See: [backend/README.md](backend/README.MD)
	- Summary: create venv; configure `.env`; `pip install -r requirements.txt`; run `uvicorn app:app --reload --host 0.0.0.0 --port 5000`.

1. IVR service (Twilio phone)
	- See: [ivr-service/README.md](ivr-service/README.md)
	- Summary: create venv; `pip install -r requirements.txt`; run `python run.py`; set your Twilio Voice webhook to `POST https://<ngrok>/voice`.

1. WhatsApp service
	- See: [whatsapp-service/README.md](whatsapp-service/README.md)
	- Summary: create venv, configure Twilio account.

## Environment variables (at a glance)

- Backend: `MISTRAL_API_KEY`, `MODEL_NAME`, Redis settings; optional `AGRO_API_KEY`, `DATA_GOV_API_KEY`.
- IVR: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_NUMBER`, `GROQ_API_KEY`; optional `ELEVENLABS_API_KEY`.

## Contributing

- Open an issue before large changes.
- Use feature branches and concise PRs. Reference issues in commit messages.
- Follow existing style and keep config in `.env` files (never commit secrets).

### Dev tips

- Windows PowerShell friendly commands are used throughout the READMEs.
- Keep the backend on port 5000; IVR `run.py` expects it for `/response`.
- For ngrok, prefer HTTPS tunnels for Twilio webhooks.

## License

MIT (or project default). Please check repository settings for the current license.

