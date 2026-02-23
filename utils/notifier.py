import requests
import json
import os

class DiscordNotifier:
    """Sends event alerts to a Discord channel via Webhook."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def notify(self, event: dict):
        """Formats and sends an event to Discord."""
        if not self.webhook_url:
            print("No Discord Webhook URL provided. Skipping notification.")
            return

        payload = {
            "embeds": [{
                "title": f"🍕 Free Food Alert: {event['title']}",
                "description": event['description'][:200] + "...",
                "url": event['link'],
                "color": 15158332, # Red
                "fields": [
                    {"name": "Date", "value": event.get('date', 'N/A'), "inline": True},
                    {"name": "Keyword Found", "value": event.get('food_keyword', 'food'), "inline": True},
                    {"name": "Source", "value": event.get('source', 'Unknown'), "inline": True}
                ],
                "footer": {"text": "Campus Food Scraper Bot"}
            }]
        }

        try:
            response = requests.post(
                self.webhook_url, 
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Error sending Discord notification: {e}")
