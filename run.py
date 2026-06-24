"""
Entry point for Render.
Starts the Flask web server in a background thread, then runs the Pyrogram bot.
"""
import threading
import logging
from server import run as run_server

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Start web server in background thread (keeps Render port alive)
t = threading.Thread(target=run_server, daemon=True)
t.start()
print("✅ Web server started in background")

# Start the Telegram bot (blocking)
from main import app
print("🤖 Starting Telegram bot...")
app.run()
