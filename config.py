import os
from dotenv import load_dotenv

load_dotenv()

LAST_PAYLOAD = "last_payload.json"

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

# Basic validation
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable is not set. Please set it in your .env file.")
if not DB_NAME:
    raise ValueError("DB_NAME environment variable is not set. Please set it in your .env file.")