import asyncio
import logging
import os
import re
import time
from json import load
from os import environ, remove
from threading import Thread
from urllib.parse import urlparse

from pyrogram import Client, filters
from pyrogram.types import (
    BotCommand, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, CallbackQuery,
)
from urlextract import URLExtract

import bypasser
import freewall
from texts import HELP_TEXT
from database import (
    get_user, update_user, all_user_ids, user_count,
    load_users, load_settings, save_settings, get_setting, set_setting,
)
from middleware import (
    is_owner, is_admin, is_vip, is_banned,
    cooldown_left, daily_status, record_usage,
)

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────
with open("config.json", "r") as f:
    DATA = load(f)

def getenv(var):
    return environ.get(var) or DATA.get(var) or None

TOKEN    = getenv("TOKEN")
API_ID   = getenv("ID")
API_HASH = getenv("HASH")
OWNER_ID = int(getenv("OWNER_ID") or 0)

# ── Pyrogram client ───────────────────────────────────────────────────────
app = Client("bypass_bot", api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN)

# ── URL extractor ─────────────────────────────────────────────────────────
extractor = URLExtract()
URL_REGEX = r'(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]*'

# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def extract_urls(message: Message) -> list:
    text = message.text or message.caption or ""
    entities = message.entities or message.caption_entities or []
    urls = []
    for e in entities:
        etype = str(e.type).split(".")[-1].lower()
        if etype == "url":
            urls.append(text[e.offset: e.offset + e.length])
        elif etype == "text_link" and e.url:
            urls.append(e.url)
    urls += extractor.find_urls(text)
    urls += re.findall(URL_REGEX, text)
    cleaned = []
    for u in urls:
        u = u.strip(".,").rstrip("/")
        if u and u not in cleaned:
            cleaned.append(u)
    normalized = []
    for u in cleaned:
        if not u.startswith(("http://", "https://")):
            u = "https://" + u
        normalized.append(u)
    return normalized


def resolve_uid(arg: str):
    """Resolve user id from int string or @username."""
    try:
        return int(arg)
    except ValueError:
        uname = arg.lstrip("@").lower()
        for uid, u in load_users().items():
            if str(u.get("username", "")).lower() == uname:
                return int(uid)
    return None


async def delete_after(client, chat_id, msg_ids, delay=600):
    await asyncio.sleep(delay)
    for mid in msg_ids:
        try:
            await client.delete_messages(chat_id, mid)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────
# Force-join helpers
# ─────────────────────────────────────────────────────────────────────────

async def check_force_join(client: Client, user_id: int):
    channels = get_setting("force_join_channels")
    not_joined = []
    for ch in channels:
        try:
            member = await client.get_chat_member(ch["id"], user_id)
            if member.status.value in ("left", "kicked", "banned"):
                not_joined.append(ch)
        except Exception:
            not_joined.append(ch)
    return not_joined


def fj_keyboard(not_joined):
    buttons = [[InlineKeyboardButton(
        f"➕ Join {ch.get('title', str(ch['id']))}",
        url=ch.get("invite_link", f"https://t.me/{str(ch['id']).lstrip('@')}")
    )] for ch in not_joined]
    buttons.append([InlineKeyboardButton("✅ Done — Check Again", callback_data="check_join")])
    return InlineKeyboardMarkup(buttons)


# ─────────────────────────────────────────────────────────────────────────
# Bypass logic (from original main.py)
# ─────────────────────────────────────────────────────────────────────────

def handle_index(ele, message: Message, msg: Message):
    result = bypasser.scrapeIndex(ele)
    try:
        app.delete_messages(message.chat.id, msg.id)
    except Exception:
        pass
    if result:
        for page in result:
            app.send_message(
                message.chat.id, page,
                reply_to_message_id=message.id,
                disable_web_page_preview=True,
            )


def do_bypass(message: Message, otherss=False):
    """Core bypass logic — runs in a thread."""
    urls = extract_urls(message)
    if not urls:
        app.send_message(message.chat.id, "❌ No valid URLs found.", reply_to_message_id=message.id)
        return

    first = urls[0]
    if bypasser.ispresent(bypasser.ddl.ddllist, first):
        msg = app.send_message(message.chat.id, "⚡ __generating...__", reply_to_message_id=message.id)
    elif freewall.pass_paywall(first, check=True):
        msg = app.send_message(message.chat.id, "🕴️ __jumping the wall...__", reply_to_message_id=message.id)
    elif "olamovies" in first or "psa.wf" in first:
        msg = app.send_message(message.chat.id, "⏳ __this might take some time...__", reply_to_message_id=message.id)
    else:
        msg = app.send_message(message.chat.id, "🔎 __bypassing...__", reply_to_message_id=message.id)

    strt = time.time()
    links = ""

    for ele in urls:
        temp = None
        custom = get_setting("custom_bypasses") or {}
        parsed_domain = urlparse(ele).netloc.lower().lstrip("www.")

        if re.search(r"https?:\/\/(?:[\w.-]+)?\.\\w+\/\d+:", ele):
            handle_index(ele, message, msg)
            return
        elif bypasser.ispresent(bypasser.ddl.ddllist, ele):
            try:
                temp = bypasser.ddl.direct_link_generator(ele)
            except Exception as e:
                temp = f"**Error**: {e}"
        elif freewall.pass_paywall(ele, check=True):
            freefile = freewall.pass_paywall(ele)
            if freefile:
                try:
                    app.send_document(message.chat.id, freefile, reply_to_message_id=message.id)
                    remove(freefile)
                    app.delete_messages(message.chat.id, [msg.id])
                    return
                except Exception:
                    pass
            else:
                app.send_message(message.chat.id, "__Failed to Jump__", reply_to_message_id=message.id)
        else:
            try:
                temp = bypasser.shortners(ele)
            except Exception as e:
                temp = f"**Error**: {e}"

        if temp:
            links += str(temp) + "\n"

    elapsed = time.time() - strt
    logger.info(f"Bypassed in {elapsed:.2f}s")

    try:
        final_chunks = []
        tmp = ""
        for line in links.split("\n"):
            tmp += line + "\n"
            if len(tmp) > 4000:
                final_chunks.append(tmp)
                tmp = ""
        final_chunks.append(tmp)

        app.delete_messages(message.chat.id, msg.id)
        reply_ids = [message.id]
        for chunk in final_chunks:
            if chunk.strip():
                sent = app.send_message(
                    message.chat.id,
                    f"__{chunk}__",
                    reply_to_message_id=message.id,
                    disable_web_page_preview=True,
                )
                reply_ids.append(sent.id)

        # Schedule auto-delete after 10 minutes
        asyncio.run_coroutine_threadsafe(
            delete_after(app, message.chat.id, reply_ids, 600),
            asyncio.get_event_loop()
        )

    except Exception as e:
        app.send_message(message.chat.id, f"__Failed to Bypass: {e}__", reply_to_message_id=message.id)


# ─────────────────────────────────────────────────────────────────────────
# Guard decorator
# ─────────────────────────────────────────────────────────────────────────

def user_guard(func):
    """Runs standard checks: banned, maintenance, force-join, cooldown, limit."""
    async def wrapper(client: Client, message: Message):
        uid = message.from_user.id
        get_user(uid)

        if is_banned(uid):
            await message.reply("🚫 You are banned from using this bot.")
            return

        admin = is_admin(uid, OWNER_ID)
        vip   = is_vip(uid)

        if get_setting("maintenance") and not admin:
            await message.reply("🔧 *Bot is under maintenance.* Please try again later.", parse_mode="MARKDOWN")
            return

        if not admin:
            not_joined = await check_force_join(client, uid)
            if not_joined:
                await message.reply(
                    "⚠️ *You must join our channels to use this bot!*",
                    parse_mode="MARKDOWN",
                    reply_markup=fj_keyboard(not_joined),
                )
                return

        if not admin and not vip:
            cd = cooldown_left(uid)
            if cd > 0:
                m = await message.reply(f"⏳ *Cooldown!* Please wait *{cd}s*.", parse_mode="MARKDOWN")
                asyncio.create_task(delete_after(client, message.chat.id, [m.id], 10))
                return
            hit, count, limit = daily_status(uid)
            if hit:
                m = await message.reply(
                    f"📛 *Daily limit reached!* {count}/{limit} used today.\nResets in 24h.",
                    parse_mode="MARKDOWN"
                )
                asyncio.create_task(delete_after(client, message.chat.id, [m.id], 30))
                return

        return await func(client, message)
    wrapper.__name__ = func.__name__
    return wrapper


# ─────────────────────────────────────────────────────────────────────────
# User commands
# ─────────────────────────────────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def cmd_start(client: Client, message: Message):
    uid = message.from_user.id
    get_user(uid)
    admin = is_admin(uid, OWNER_ID)

    if not admin:
        not_joined = await check_force_join(client, uid)
        if not_joined:
            await message.reply(
                "⚠️ *You must join our channels to use this bot!*\nJoin all channels below, then click Done.",
                parse_mode="MARKDOWN",
                reply_markup=fj_keyboard(not_joined),
            )
            return

    await message.reply(
        f"👋 Hi **{message.from_user.mention}**!\n\n"
        "🔗 *Link Bypasser Bot* — Send me any supported shortlink and I'll get you the real link.\n\n"
        "📌 Send /help to see all supported sites.",
        parse_mode="MARKDOWN",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌐 Source Code", url="https://github.com/bipinkrish/Link-Bypasser-Bot")
        ]]),
    )


@app.on_message(filters.command("help"))
async def cmd_help(client: Client, message: Message):
    await message.reply(HELP_TEXT, disable_web_page_preview=True)


@app.on_callback_query(filters.regex("^check_join$"))
async def cb_check_join(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    not_joined = await check_force_join(client, uid)
    if not_joined:
        await query.edit_message_text(
            "❌ *You haven't joined all channels yet!* Please join and try again.",
            parse_mode="MARKDOWN",
            reply_markup=fj_keyboard(not_joined),
        )
    else:
        await query.edit_message_text(
            "✅ *Great!* You've joined all channels.\nNow send me any link to bypass!",
            parse_mode="MARKDOWN",
        )
    await query.answer()


# ─────────────────────────────────────────────────────────────────────────
# Link handlers
# ─────────────────────────────────────────────────────────────────────────

@app.on_message(filters.text & ~filters.command(["start","help","stats","maintenance",
    "setcooldown","removecooldown","setlimit","removelimit","addadmin","removeadmin",
    "addvip","removevip","ban","unban","broadcast","addforcejoin","removeforcejoin",
    "addbypass","removebypass"]))
@user_guard
async def handle_text(client: Client, message: Message):
    record_usage(message.from_user.id)
    Thread(target=do_bypass, args=(message,), daemon=True).start()


@app.on_message(filters.document | filters.photo | filters.video)
@user_guard
async def handle_media(client: Client, message: Message):
    try:
        if message.document and message.document.file_name.endswith("dlc"):
            def dlc_thread():
                msg = app.send_message(message.chat.id, "🔎 __bypassing DLC...__", reply_to_message_id=message.id)
                file = app.download_media(message)
                content = open(file, "r").read()
                links = bypasser.getlinks(content)
                app.edit_message_text(message.chat.id, msg.id, f"__{links}__", disable_web_page_preview=True)
                remove(file)
            record_usage(message.from_user.id)
            Thread(target=dlc_thread, daemon=True).start()
            return
    except Exception:
        pass
    record_usage(message.from_user.id)
    Thread(target=lambda: do_bypass(message, True), daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────
# Admin commands
# ─────────────────────────────────────────────────────────────────────────

def admin_check(uid):
    return is_admin(uid, OWNER_ID)

def owner_check(uid):
    return is_owner(uid, OWNER_ID)


@app.on_message(filters.command("stats"))
async def cmd_stats(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    users = load_users()
    total  = len(users)
    banned = sum(1 for u in users.values() if u.get("banned"))
    vips   = sum(1 for u in users.values() if u.get("vip"))
    admins = len(get_setting("admins"))
    maint  = "🔴 ON" if get_setting("maintenance") else "🟢 OFF"
    cd     = get_setting("cooldown_seconds")
    lim    = get_setting("daily_limit")
    fj     = len(get_setting("force_join_channels"))
    cb     = len(get_setting("custom_bypasses"))
    await message.reply(
        f"📊 **Bot Statistics**\n\n"
        f"👥 Total Users: `{total}`\n"
        f"🚫 Banned: `{banned}`\n"
        f"⭐ VIP: `{vips}`\n"
        f"🛡️ Admins: `{admins}`\n"
        f"🔧 Maintenance: {maint}\n"
        f"⏳ Cooldown: `{cd}s`\n"
        f"📛 Daily Limit: `{lim}`\n"
        f"📢 Force Join Channels: `{fj}`\n"
        f"🔗 Custom Bypasses: `{cb}`",
        parse_mode="MARKDOWN",
    )


@app.on_message(filters.command("maintenance"))
async def cmd_maintenance(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.command[1:]
    if not args or args[0].lower() not in ("on", "off"):
        return await message.reply("Usage: /maintenance on|off")
    val = args[0].lower() == "on"
    set_setting("maintenance", val)
    await message.reply(f"🔧 Maintenance mode: {'*ON*' if val else '*OFF*'}", parse_mode="MARKDOWN")


@app.on_message(filters.command("setcooldown"))
async def cmd_setcooldown(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /setcooldown <seconds>")
    try:
        secs = int(args[0])
        set_setting("cooldown_seconds", secs)
        await message.reply(f"✅ Cooldown set to *{secs}s*.", parse_mode="MARKDOWN")
    except ValueError:
        await message.reply("❌ Invalid number.")


@app.on_message(filters.command("removecooldown"))
async def cmd_removecooldown(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    set_setting("cooldown_seconds", 0)
    await message.reply("✅ Cooldown *removed*.", parse_mode="MARKDOWN")


@app.on_message(filters.command("setlimit"))
async def cmd_setlimit(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /setlimit <number>")
    try:
        n = int(args[0])
        set_setting("daily_limit", n)
        await message.reply(f"✅ Daily limit set to *{n}*.", parse_mode="MARKDOWN")
    except ValueError:
        await message.reply("❌ Invalid number.")


@app.on_message(filters.command("removelimit"))
async def cmd_removelimit(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    set_setting("daily_limit", 0)
    await message.reply("✅ Daily limit *removed*.", parse_mode="MARKDOWN")


@app.on_message(filters.command("addadmin"))
async def cmd_addadmin(client: Client, message: Message):
    if not owner_check(message.from_user.id):
        return await message.reply("❌ Owner only.")
    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /addadmin <user_id|@username> [days]")
    uid = resolve_uid(args[0])
    if not uid:
        return await message.reply("❌ User not found in database.")
    days   = int(args[1]) if len(args) > 1 else 0
    expiry = int(time.time()) + days * 86400 if days else 0
    s = load_settings()
    s["admins"] = [a for a in s["admins"] if a["id"] != uid]
    s["admins"].append({"id": uid, "expiry": expiry})
    save_settings(s)
    dur = f"{days} days" if days else "permanent"
    await message.reply(f"✅ `{uid}` added as admin ({dur}).", parse_mode="MARKDOWN")
    try:
        await client.send_message(uid, f"🛡️ You have been *added as Admin* ({dur}).", parse_mode="MARKDOWN")
    except Exception:
        pass


@app.on_message(filters.command("removeadmin"))
async def cmd_removeadmin(client: Client, message: Message):
    if not owner_check(message.from_user.id):
        return await message.reply("❌ Owner only.")
    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /removeadmin <user_id|@username>")
    uid = resolve_uid(args[0])
    if not uid:
        return await message.reply("❌ User not found.")
    s = load_settings()
    before = len(s["admins"])
    s["admins"] = [a for a in s["admins"] if a["id"] != uid]
    save_settings(s)
    if len(s["admins"]) < before:
        await message.reply(f"✅ `{uid}` removed from admins.", parse_mode="MARKDOWN")
        try:
            await client.send_message(uid, "🚫 Your *Admin access* has been removed.", parse_mode="MARKDOWN")
        except Exception:
            pass
    else:
        await message.reply("❌ User was not an admin.")


@app.on_message(filters.command("addvip"))
async def cmd_addvip(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /addvip <user_id|@username> [days]")
    uid = resolve_uid(args[0])
    if not uid:
        return await message.reply("❌ User not found in database.")
    days   = int(args[1]) if len(args) > 1 else 0
    expiry = int(time.time()) + days * 86400 if days else 0
    update_user(uid, {"vip": True, "vip_expiry": expiry})
    dur = f"{days} days" if days else "permanent"
    await message.reply(f"⭐ `{uid}` is now VIP ({dur}).", parse_mode="MARKDOWN")
    try:
        await client.send_message(
            uid,
            f"⭐ *Congratulations!* You've been granted *VIP* access ({dur}).\nEnjoy unlimited bypasses!",
            parse_mode="MARKDOWN"
        )
    except Exception:
        pass


@app.on_message(filters.command("removevip"))
async def cmd_removevip(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /removevip <user_id|@username>")
    uid = resolve_uid(args[0])
    if not uid:
        return await message.reply("❌ User not found.")
    update_user(uid, {"vip": False, "vip_expiry": 0})
    await message.reply(f"✅ VIP removed from `{uid}`.", parse_mode="MARKDOWN")
    try:
        await client.send_message(uid, "❌ Your *VIP access* has been removed.", parse_mode="MARKDOWN")
    except Exception:
        pass


@app.on_message(filters.command("ban"))
async def cmd_ban(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /ban <user_id|@username>")
    uid = resolve_uid(args[0])
    if not uid:
        return await message.reply("❌ User not found.")
    update_user(uid, {"banned": True})
    await message.reply(f"🚫 `{uid}` has been *banned*.", parse_mode="MARKDOWN")


@app.on_message(filters.command("unban"))
async def cmd_unban(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /unban <user_id|@username>")
    uid = resolve_uid(args[0])
    if not uid:
        return await message.reply("❌ User not found.")
    update_user(uid, {"banned": False})
    await message.reply(f"✅ `{uid}` has been *unbanned*.", parse_mode="MARKDOWN")


@app.on_message(filters.command("broadcast"))
async def cmd_broadcast(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    text = ""
    if message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
    elif len(message.command) > 1:
        text = message.text.split(None, 1)[1]
    if not text:
        return await message.reply("Usage: /broadcast <message>  OR  reply to a message with /broadcast")
    ids = all_user_ids()
    sent = failed = 0
    status = await message.reply(f"📢 Broadcasting to {len(ids)} users...")
    for uid in ids:
        try:
            await client.send_message(uid, f"📢 **Broadcast**\n\n{text}", parse_mode="MARKDOWN")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await status.edit(f"✅ *Broadcast done!*\n\n✉️ Sent: `{sent}`\n❌ Failed: `{failed}`", parse_mode="MARKDOWN")


@app.on_message(filters.command("addforcejoin"))
async def cmd_addforcejoin(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.command[1:]
    if not args:
        return await message.reply(
            "Usage: /addforcejoin <@username or channel_id>\n\n⚠️ Make bot *admin* in the channel first!",
            parse_mode="MARKDOWN"
        )
    identifier = args[0].strip()
    try:
        chat = await client.get_chat(identifier)
        invite = chat.invite_link
        if not invite:
            invite = f"https://t.me/{chat.username}" if chat.username else str(chat.id)
        entry = {"id": chat.id, "title": chat.title or identifier, "invite_link": invite}
        s = load_settings()
        s["force_join_channels"] = [c for c in s["force_join_channels"] if c["id"] != chat.id]
        s["force_join_channels"].append(entry)
        save_settings(s)
        await message.reply(
            f"✅ Added *{chat.title}* to force join.\nTotal: `{len(s['force_join_channels'])}` channel(s)",
            parse_mode="MARKDOWN"
        )
    except Exception as e:
        await message.reply(f"❌ Error: {e}\n\nMake sure bot is admin in that channel.")


@app.on_message(filters.command("removeforcejoin"))
async def cmd_removeforcejoin(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    channels = get_setting("force_join_channels")
    if not channels:
        return await message.reply("No force join channels set.")
    args = message.command[1:]
    if not args:
        lst = "\n".join([f"• `{c['id']}` — {c['title']}" for c in channels])
        return await message.reply(
            f"📢 **Force Join Channels:**\n{lst}\n\nUsage: /removeforcejoin <channel_id>",
            parse_mode="MARKDOWN"
        )
    identifier = args[0].strip()
    s = load_settings()
    before = len(s["force_join_channels"])
    s["force_join_channels"] = [
        c for c in s["force_join_channels"]
        if str(c["id"]) != identifier and c.get("title") != identifier
    ]
    if len(s["force_join_channels"]) < before:
        save_settings(s)
        await message.reply("✅ Channel removed from force join list.")
    else:
        await message.reply("❌ Channel not found in list.")


@app.on_message(filters.command("addbypass"))
async def cmd_addbypass(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    args = message.command[1:]
    if not args:
        return await message.reply("Usage: /addbypass <domain>\nExample: /addbypass example-shortener.com")
    domain = args[0].lower().lstrip("www.")
    s = load_settings()
    s["custom_bypasses"][domain] = "generic"
    save_settings(s)
    await message.reply(f"✅ `{domain}` added. The bot will now attempt to bypass links from this domain.", parse_mode="MARKDOWN")


@app.on_message(filters.command("removebypass"))
async def cmd_removebypass(client: Client, message: Message):
    if not admin_check(message.from_user.id):
        return await message.reply("❌ Admins only.")
    customs = get_setting("custom_bypasses") or {}
    args = message.command[1:]
    if not args:
        if not customs:
            return await message.reply("No custom bypasses added.")
        lst = "\n".join([f"• `{d}`" for d in customs])
        return await message.reply(f"🔗 **Custom Bypasses:**\n{lst}\n\nUsage: /removebypass <domain>", parse_mode="MARKDOWN")
    domain = args[0].lower().lstrip("www.")
    s = load_settings()
    if domain in s["custom_bypasses"]:
        del s["custom_bypasses"][domain]
        save_settings(s)
        await message.reply(f"✅ `{domain}` removed.", parse_mode="MARKDOWN")
    else:
        await message.reply("❌ Domain not found in custom list.")


# ─────────────────────────────────────────────────────────────────────────
# Group auto-leave
# ─────────────────────────────────────────────────────────────────────────

@app.on_message(filters.new_chat_members)
async def auto_leave(client: Client, message: Message):
    bot_me = await client.get_me()
    for member in message.new_chat_members:
        if member.id == bot_me.id:
            adder = message.from_user
            if adder and is_owner(adder.id, OWNER_ID):
                return
            try:
                await message.reply("⚠️ I only work in private chats. Leaving now...")
            except Exception:
                pass
            try:
                await client.leave_chat(message.chat.id)
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Bot starting...")
    app.run()
       
