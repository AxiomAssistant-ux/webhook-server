from pymongo import MongoClient
from config import MONGO_URI, DB_NAME

# Global client and database instances
client = None
db = None

def connect_to_mongo():
    """Initializes the MongoDB client and database connection."""
    global client, db
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        # Test connection
        client.admin.command('ping')
        print("Successfully connected to MongoDB Atlas!")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        # Handle connection error appropriately
        raise

def get_database():
    """Returns the database instance. Connects if not already connected."""
    if db is None:
        connect_to_mongo()
    return db

def close_mongo_connection():
    """Closes the MongoDB connection."""
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")