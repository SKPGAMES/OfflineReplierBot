import logging
import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ===== CONFIG =====
import os
BOT_TOKEN = os.environ.get("8321132793:AAGuH9lF_GMyYh2EYlvjt29M9m_dN01_r8U")
if not BOT_TOKEN:
    raise ValueError("Bot token not set. Please set BOT_TOKEN environment variable.")
ADMIN_IDS = [5665364113]  # Replace with your Telegram user ID(s)
OFFLINE_FILE = "offline_status.txt"
REPLIES_FILE = "custom_replies.txt"
FORWARD_MAP = {}  # Temporary map user_id <-> admin_msg_id for reply tracking

# ===== LOGGER =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ===== STATE HELPERS =====
def is_offline():
    return os.path.exists(OFFLINE_FILE)

def set_offline(value: bool):
    if value:
        open(OFFLINE_FILE, "w").close()
    else:
        if os.path.exists(OFFLINE_FILE):
            os.remove(OFFLINE_FILE)

def get_custom_reply():
    if not os.path.exists(REPLIES_FILE):
        return "💬 The admin is currently offline. I’ll pass your message along when they’re back!"
    with open(REPLIES_FILE, "r", encoding="utf-8") as f:
        return f.read().strip() or "💬 The admin is currently offline."

def set_custom_reply(text: str):
    with open(REPLIES_FILE, "w", encoding="utf-8") as f:
        f.write(text)

# ===== COMMANDS =====
async def cmd_online(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ You are not authorized.")
    set_offline(False)
    await update.message.reply_text("✅ Bot is now in ONLINE mode (admin replies manually).")

async def cmd_offline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ You are not authorized.")
    set_offline(True)
    await update.message.reply_text("🤖 Bot is now in OFFLINE mode (auto-replies enabled).")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "🟢 ONLINE" if not is_offline() else "🔴 OFFLINE"
    await update.message.reply_text(f"Current mode: {status}")

async def cmd_setreply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("❌ You are not authorized.")
    text = " ".join(context.args)
    if not text:
        return await update.message.reply_text("Usage: /setreply <custom offline message>")
    set_custom_reply(text)
    await update.message.reply_text("✅ Custom offline reply message updated.")

# ===== DELETE JOIN/LEFT MESSAGES =====
async def delete_system_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.new_chat_members or msg.left_chat_member:
        try:
            await msg.delete()
            logger.info("Deleted system message.")
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")

# ===== AUTO REPLY + FORWARD =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or msg.from_user.is_bot:
        return

    user = msg.from_user
    text = msg.text or "<non-text message>"

    # If admin replies to forwarded message -> send back to original user
    if user.id in ADMIN_IDS and msg.reply_to_message:
        for uid, mid in list(FORWARD_MAP.items()):
            if msg.reply_to_message.message_id == mid:
                try:
                    await context.bot.send_message(uid, f"👤 Admin: {msg.text}")
                    await update.message.reply_text("✅ Message delivered to user.")
                except Exception as e:
                    await update.message.reply_text(f"⚠️ Failed to deliver: {e}")
                return

    # Handle user message when offline
    if is_offline():
        reply_text = get_custom_reply()
        await msg.reply_text(reply_text)

        # Forward message to admin(s)
        for admin_id in ADMIN_IDS:
            sent = await context.bot.send_message(
                chat_id=admin_id,
                text=f"📨 Message from @{user.username or user.first_name} ({user.id}):\n\n{text}"
            )
            FORWARD_MAP[user.id] = sent.message_id
            logger.info(f"Forwarded message from {user.id} to admin {admin_id}.")

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("online", cmd_online))
    app.add_handler(CommandHandler("offline", cmd_offline))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("setreply", cmd_setreply))

    app.add_handler(MessageHandler(filters.StatusUpdate.ALL, delete_system_messages))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot v2 running with forwarding + custom replies...")
    app.run_polling()

if __name__ == "__main__":
    main()
