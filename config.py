import os
from dotenv import load_dotenv

load_dotenv()

SUMMARY_FILE = "summary.json"
LAST_PAYLOAD = "last_payload.json"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") 

if not WEBHOOK_SECRET:
    raise ValueError("WEBHOOK_SECRET environment variable is not set. Please set it in your .env file.")