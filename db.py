# db.py (Motor/async)
import sys
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import OperationFailure, ConfigurationError, ConnectionFailure
from config import MONGO_URI, DB_NAME

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None

async def connect_to_mongo() -> AsyncIOMotorDatabase:
    """Create a global Motor client and verify auth."""
    global _client, _db
    try:
        _client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        # Force a round-trip to ensure auth/URI are correct
        await _client.admin.command("ping")
        _db = _client.get_database(DB_NAME)
        print("✅ MongoDB connected (Motor).")
        return _db
    except OperationFailure as e:
        print(f"❌ Auth failed: {e}", file=sys.stderr)
        raise
    except (ConfigurationError, ConnectionFailure) as e:
        print(f"❌ Connection/Config error: {e}", file=sys.stderr)
        raise

def get_database() -> AsyncIOMotorDatabase:
    """Return the global DB handle (after startup)."""
    if _db is None:
        raise RuntimeError("Database not initialized. Did you call connect_to_mongo() at startup?")
    return _db

async def close_mongo_connection():
    """Close the Motor client cleanly on shutdown."""
    global _client, _db
    if _client is not None:
        _client.close()
    _client, _db = None, None
    print("🛑 MongoDB connection closed.")
