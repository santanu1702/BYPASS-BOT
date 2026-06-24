"""
Minimal web server to keep Render happy (no "no open ports" error).
Runs in a separate thread alongside the Pyrogram bot.
"""
from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "<h2>✅ Link Bypasser Bot is Running</h2>", 200

@app.route("/health")
def health():
    return "OK", 200

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)
