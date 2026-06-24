"""
Render entry point.
1. Fixes Pyrogram lowercase parse mode issue via monkey-patch safety net.
2. Starts Flask web server on $PORT in a background thread (satisfies Render)
3. Starts the Pyrogram Telegram bot (blocking main thread)
"""
import threading
import logging
import os

# --- MONKEY PATCH SAFETY NET ---
# This intercepts Pyrogram handlers before they launch and redirects 
# lowercase 'markdown' to its proper uppercase variant globally.
try:
    import pyrogram
    from pyrogram.parser import Parser
    
    _old_parse = Parser.parse
    def safe_parse(self, text, parse_mode, *args, **kwargs):
        if isinstance(parse_mode, str) and parse_mode.lower() == "markdown":
            parse_mode = "MARKDOWN"
        return _old_parse(self, text, parse_mode, *args, **kwargs)
    
    Parser.parse = safe_parse
except Exception:
    pass
# -------------------------------

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
