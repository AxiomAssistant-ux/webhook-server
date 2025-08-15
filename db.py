from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME

# Global client and database instances
client = None
db = None

async def connect_to_mongo():
    """Initializes the MongoDB client and database connection."""
    global client, db
    try:
        client = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000  # Fail fast if no connection
        )
        db = client[DB_NAME]
        # Test connection
        await db.command("ping")
        print("✅ Successfully connected to MongoDB Atlas!")
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        raise

def get_database():
    """Returns the database instance. Assumes already connected."""
    if db is None:
        raise RuntimeError("Database connection is not initialized. Call connect_to_mongo first.")
    return db

async def close_mongo_connection():
    """Closes the MongoDB connection."""
    global client
    if client:
        client.close()
        print("🔌 MongoDB connection closed.")
