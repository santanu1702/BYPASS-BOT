"""
Minimal web server to satisfy Render's port requirement.
Runs in a background thread alongside the Pyrogram bot.
"""
from flask import Flask
import os

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "<h2>✅ Link Bypasser Bot is Running</h2>", 200

@flask_app.route("/health")
def health():
    return "OK", 200

def run():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False, threaded=True)
    
