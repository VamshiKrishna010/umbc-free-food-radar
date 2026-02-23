from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from pymongo import MongoClient
import certifi
from dotenv import load_dotenv
import json
import os
from main import main as run_scraper

load_dotenv()

app = Flask(__name__, static_folder='static')
CORS(app)

# MongoDB Setup
MONGO_URI = os.getenv("MONGO_URI")
print(f"DEBUG: app.py MONGO_URI starts with: {str(MONGO_URI)[:15] if MONGO_URI else 'None'}", flush=True)

# Connect to MongoDB. If this fails, the app will intentionally crash 
# so Render restarts it until the database is available.
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsCAFile=certifi.where())
# Test connection explicitly
client.server_info()
print("Successfully connected to MongoDB!", flush=True)

db = client.umbc_food_radar
events_collection = db.events

def scheduled_scraping():
    print("Running scheduled background scrape...")
    try:
        run_scraper()
        print("Background scrape completed successfully.")
    except Exception as e:
        print(f"Error during background scrape: {e}")

from datetime import datetime

# Initialize and start the background scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=scheduled_scraping, trigger="interval", minutes=15, next_run_time=datetime.now())
scheduler.start()

@app.route('/')
def index():
    """Serve the main dashboard page."""
    return send_from_directory('static', 'index.html')

@app.route('/api/events')
def get_events():
    """API endpoint to get the latest scraped events."""
    if db is not None:
        try:
            # Find all events, excluding the MongoDB _id field since it's not JSON serializable by default
            events = list(events_collection.find({}, {'_id': 0}))
            return jsonify(events)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify([])

if __name__ == '__main__':
    # Run the app on all interfaces, port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
