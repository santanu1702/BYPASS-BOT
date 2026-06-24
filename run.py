"""
Render entry point.
1. Starts Flask web server on $PORT in a background thread (satisfies Render)
2. Starts the Pyrogram Telegram bot (blocking main thread)
"""
import threading
import logging
import os

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# Start web server in background thread FIRST so Render sees the port
from server import run as run_server
t = threading.Thread(target=run_server, daemon=True)
t.start()
log.info(f"✅ Web server started on port {os.environ.get('PORT', 8080)}")

# Now start the bot (this blocks forever)
from main import app
log.info("🤖 Starting Telegram bot...")
app.run()
