from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import json
import os
from main import main as run_scraper

app = Flask(__name__, static_folder='static')
CORS(app)

EVENTS_DATA_FILE = "events_data.json"

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
    if os.path.exists(EVENTS_DATA_FILE):
        try:
            with open(EVENTS_DATA_FILE, 'r') as f:
                events = json.load(f)
                return jsonify(events)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify([])

if __name__ == '__main__':
    # Run the app on all interfaces, port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
