import os
import json
import logging
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import re
import time
import hashlib
import threading
from flask import Flask
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup Flask Dummy Server for Render Free Tier Port Binding
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


# Enable Telebot logging for diagnostics
telebot.logger.setLevel(logging.INFO)

# Configuration from environment variables
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = os.getenv("ADMINS")
BIN_CHANNEL = os.getenv("BIN_CHANNEL")
AUTO_FFILTER = os.getenv("AUTO_FFILTER", "True") == "True"
SPELL_CHECK_REPLY = os.getenv("SPELL_CHECK_REPLY", "True") == "True"
BUTTON_MODE = os.getenv("BUTTON_MODE", "True") == "True"
API_KEY = os.getenv("SHORTENER_API")
SHORTENER_WEBSITE = os.getenv("SHORTENER_WEBSITE", "indianshortner.com")
IS_VERIFY = os.getenv("IS_VERIFY", "True") == "True"

SHORTENER_API_URL = f"https://{SHORTENER_WEBSITE}/api"

# ==== FEATURE SETTINGS ====
# Channel joining requirement details
FORCE_JOIN_CHANNEL_ID = "@Shreyash940" # Replace with your actual channel username later (e.g., @MyChannel)
CHANNEL_INVITE_LINK = "https://t.me/Shreyash940" # Link button for users

# Admin Setup: Put your numeric Telegram Chat ID here to receive movie requests!
ADMIN_CHAT_ID = int(ADMINS) if ADMINS and ADMINS.isdigit() else 0

# Link to a video tutorial showing how to verify (e.g., a Telegram message link or YouTube link)
HOW_TO_VERIFY_VIDEO_URL = "https://t.me/c/3981306919/2" # Replace with your actual video link
# ==========================

def generate_verify_token(user_id):
    SECRET = "MovieWorldSecret99"
    hash_obj = hashlib.md5(f"{user_id}{SECRET}".encode())
    return f"verify_{user_id}_{hash_obj.hexdigest()[:8]}"

# Initialize the Telebot Client
bot = telebot.TeleBot(BOT_TOKEN)

# File to store our movie database
DB_FILE = "movies.json"
VERIFIED_USERS_FILE = "verified_users.json"
USERS_FILE = "all_users.json"

# List of Admin Telegram Usernames allowed to upload movies
# Add more usernames here if needed (without the @ symbol)
ADMIN_USERNAMES = ["jatharpatil", "shreyash_jathar"]

def load_db():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r") as f:
        try:
            db = json.load(f)
            # Make sure it's a list since we changed from dict (deep link style) to list (search style)
            if isinstance(db, dict):
                return []
            return db
        except:
            return []

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_verified_users():
    if not os.path.exists(VERIFIED_USERS_FILE):
        return {}
    with open(VERIFIED_USERS_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_verified_users(users):
    with open(VERIFIED_USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def load_all_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return []

def save_user(user_id):
    users = load_all_users()
    if user_id not in users:
        users.append(user_id)
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)

def check_membership(user_id):
    """Check if the user has joined the required channel"""
    if FORCE_JOIN_CHANNEL_ID == "":
        # Skip if they haven't updated the default channel
        return True 
    try:
        member = bot.get_chat_member(FORCE_JOIN_CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception as e:
        print(f"Membership check error: {e}")
        # If bot is not admin in channel, it throws an error. Let user pass so bot doesn't break.
        return True

def is_user_verified(user_id):
    """Check if user is verified and verification hasn't expired (12 hours)"""
    verified = load_verified_users()
    user_id_str = str(user_id)
    
    if user_id_str not in verified:
        return False
    
    # Check if 12 hours have passed (12 hours = 43200 seconds)
    last_verified_time = verified[user_id_str]
    current_time = time.time()
    hours_passed = (current_time - last_verified_time) / 3600
    
    if hours_passed >= 12:
        return False  # Verification expired
    
    return True

def mark_user_verified(user_id):
    """Mark user as verified with current timestamp"""
    verified = load_verified_users()
    user_id_str = str(user_id)
    verified[user_id_str] = time.time()
    save_verified_users(verified)

def get_hours_until_revert(user_id):
    """Get hours remaining until user needs to re-verify"""
    verified = load_verified_users()
    user_id_str = str(user_id)
    
    if user_id_str not in verified:
        return 0
    
    last_verified_time = verified[user_id_str]
    current_time = time.time()
    hours_passed = (current_time - last_verified_time) / 3600
    hours_remaining = max(0, 12 - hours_passed)
    
    return hours_remaining

# Function to shorten links using Indian Shortner
def shorten_link(long_url):
    try:
        # Standard API for AdLinkFly-based shorteners
        api_url = f"{SHORTENER_API_URL}?api={API_KEY}&url={long_url}"
        response = requests.get(api_url, timeout=5)
        try:
            data = response.json()
            if data.get("status") == "success":
                return data.get("shortenedUrl")
        except:
            pass
            
        # Fallback to the code that was originally here
        payload = {
            "url": long_url,
            "api_key": API_KEY
        }
        response = requests.post(f"{SHORTENER_API_URL}/links", json=payload, timeout=5)
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            if "short_url" in data:
                return data["short_url"]
            elif "data" in data and "short_url" in data["data"]:
                return data["data"]["short_url"]
                
        return None
    except Exception as e:
        print(f"Shortener error: {e}")
        return None

# Function to detect URLs in text
def find_urls(text):
    url_pattern = r'https?://[^\s]+'
    return re.findall(url_pattern, text)

# Feature 1: The /start command (Normal welcome message)
@bot.message_handler(commands=['start'])
def start_command(message):
    text = message.text
    user_id = message.from_user.id
    save_user(user_id) # Save user for broadcasting
    
    if not check_membership(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Join Channel 📢", url=CHANNEL_INVITE_LINK))
        bot.reply_to(message, "🛑 **You must join our channel to use this bot!**\n\nClick the button below to join, then click /start again.", reply_markup=markup, parse_mode="Markdown")
        return

    if len(text.split()) > 1:
        token = text.split()[1]
        if token.startswith("verify_"):
            user_id = message.from_user.id
            expected_token = generate_verify_token(user_id)
            if token == expected_token:
                mark_user_verified(user_id)
                bot.reply_to(message, "✅ **Verification Successful!**\n\nYou can now search for movies. Your access is valid for 12 hours. 🍿", parse_mode="Markdown")
                return
            else:
                bot.reply_to(message, "❌ **Invalid or expired verification link.**\nPlease search for a movie again to get a new link.", parse_mode="Markdown")
                return

    bot.reply_to(
        message,
        "🎬 **Welcome to the MovieWorld Bot!** 🍿\n\n"
        "**How to use:**\n"
        "Just type the **name of any movie or web series** you want to watch, and I will send you the file immediately!\n\n"
        "*(Example 1: Dhurandhar 2025)*\n"
        "*(Example 2: Mirzapur S01 E01)*\n\n"
        f"📺 **How to verify / download:** [Watch Tutorial Video]({HOW_TO_VERIFY_VIDEO_URL})",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

# Feature 1.5: Link shortener
@bot.message_handler(func=lambda message: find_urls(message.text))
def shorten_links_handler(message):
    user_id = message.from_user.id
    urls = find_urls(message.text)
    response_text = "🔗 **Shortened Links:**\n\n"
    
    for url in urls:
        shortened = shorten_link(url)
        if shortened:
            response_text += f"📎 Original: `{url}`\n"
            response_text += f"✂️ Short: `{shortened}`\n\n"
        else:
            response_text += f"❌ Failed to shorten: `{url}`\n\n"
    
    bot.reply_to(message, response_text, parse_mode="Markdown")

# ================= NEW FEATURES =================

# Feature: User Requesting a Movie
@bot.message_handler(commands=['request'])
def request_movie_command(message):
    user_id = message.from_user.id
    save_user(user_id)
    text = message.text.replace("/request", "").strip()
    
    if not text:
        bot.reply_to(message, "📝 **How to request a movie:**\nType `/request Movie Name`\n\n*Example:* `/request Inception 2010`", parse_mode="Markdown")
        return
        
    bot.reply_to(message, "✅ **Request sent to Admin!** We will try to upload it soon.")
    
    if ADMIN_CHAT_ID != 0:
        bot.send_message(ADMIN_CHAT_ID, f"📥 **New Movie Request!**\n\n**User:** {message.from_user.first_name} (`{user_id}`)\n**Request:** {text}", parse_mode="Markdown")
    else:
        print(f"Missed Request (No ADMIN_CHAT_ID set): {text} from user {user_id}")

# Feature: Admin Broadcast
@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    is_admin = (username and username.lower() in ADMIN_USERNAMES) or (user_id == ADMIN_CHAT_ID)
    if not is_admin:
        return
        
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        bot.reply_to(message, "📢 **How to broadcast:**\n`/broadcast Hello everyone, we added new movies!`", parse_mode="Markdown")
        return
        
    users = load_all_users()
    success = 0
    fail = 0
    status_msg = bot.reply_to(message, f"Broadcasting to {len(users)} users... ⏳")
    
    for uid in users:
        try:
            bot.send_message(uid, f"📢 **Announcement**\n\n{text}", parse_mode="Markdown")
            success += 1
            time.sleep(0.05) # Prevent hitting Telegram's rate limit
        except:
            fail += 1
            
    bot.edit_message_text(f"✅ **Broadcast Complete!**\n\nSuccessfully sent: {success}\nFailed: {fail}", chat_id=message.chat.id, message_id=status_msg.message_id, parse_mode="Markdown")

# Feature: Admin Delete Movie
@bot.message_handler(commands=['delete'])
def delete_movie_command(message):
    user_id = message.from_user.id
    username = message.from_user.username
    is_admin = (username and username.lower() in ADMIN_USERNAMES) or (user_id == ADMIN_CHAT_ID)
    if not is_admin:
        return
        
    text = message.text.replace("/delete", "").strip().lower()
    if not text:
        bot.reply_to(message, "🗑️ **How to delete a movie:**\n`/delete exact movie name`", parse_mode="Markdown")
        return
        
    db = load_db()
    original_length = len(db)
    
    # Keep movies that DO NOT match the exact text
    new_db = [m for m in db if m["title_lower"] != text]
    
    if len(new_db) == original_length:
        bot.reply_to(message, f"❌ Could not find a movie exactly matching `{text}`.", parse_mode="Markdown")
    else:
        save_db(new_db)
        deleted_count = original_length - len(new_db)
        bot.reply_to(message, f"✅ Successfully deleted {deleted_count} movie(s) matching '{text}'.", parse_mode="Markdown")

# ================================================

# Feature 2: Admin uploading movies to the database
@bot.message_handler(content_types=['video', 'document'])
def handle_movie_upload(message):
    # Security: Verify that the sender is our specified admin
    user_id = message.from_user.id
    username = message.from_user.username
    is_admin = (username and username.lower() in ADMIN_USERNAMES) or (user_id == ADMIN_CHAT_ID)
    
    if not is_admin:
        bot.reply_to(
            message, 
            "❌ **Upload Denied!** Only authorized admins can upload and add files.", 
            parse_mode="Markdown"
        )
        return

    # To add a movie, the uploader MUST provide a caption
    title = message.caption
    
    # Try to use file name if there is no caption
    if not title:
        if message.document and message.document.file_name:
            title = message.document.file_name.rsplit(".", 1)[0]
        elif message.video and hasattr(message.video, 'file_name') and message.video.file_name:
            title = message.video.file_name.rsplit(".", 1)[0]
        else:
            bot.reply_to(message, "❌ **Please send the media with a caption!**\nThe caption will be used as the Movie's name for users to search.")
            return

    status = bot.reply_to(message, "Adding to database... ⏳")
    
    # Grab the Telegram file_id
    if message.video:
        file_id = message.video.file_id
        file_type = "video"
    elif message.document:
        file_id = message.document.file_id
        file_type = "document"

    # Save to db
    db = load_db()
    movie_entry = {
        "title": title.strip(),
        "title_lower": title.strip().lower(),
        "file_id": file_id,
        "type": file_type
    }
    db.append(movie_entry)
    save_db(db)
    
    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=status.message_id,
        text=f"✅ **Successfully added!**\n\nUsers can now type `{title.strip()}` to get this movie instantly.",
        parse_mode="Markdown"
    )

# Feature 3: Users searching for a movie by typing text
@bot.message_handler(content_types=['text'])
def search_movie(message):
    user_id = message.from_user.id
    query = message.text.lower().strip()
    
    save_user(user_id) # Save user for broadcasting
    
    # Ignore slash commands if they slip through
    if query.startswith('/'):
        return

    if not check_membership(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Join Channel 📢", url=CHANNEL_INVITE_LINK))
        bot.reply_to(message, "🛑 **You must join our channel to use this bot!**\n\nClick the button below to join, then search for your movie again.", reply_markup=markup, parse_mode="Markdown")
        return
    
    # Check if user is verified (has verified via shortener)
    if IS_VERIFY and not is_user_verified(user_id):
        try:
            bot_info = bot.get_me()
            bot_username = bot_info.username
        except Exception as e:
            bot.reply_to(message, "Error generating verification link. Please try again later.")
            return

        token = generate_verify_token(user_id)
        verify_url = f"https://t.me/{bot_username}?start={token}"
        short_url = shorten_link(verify_url)
        
        if not short_url:
            short_url = verify_url # Fallback if shortener is down
            
        bot.reply_to(
            message,
            "🔒 **Verification Required!**\n\n"
            "To prevent spam and support the bot, please verify your access.\n\n"
            "📝 **How to verify:**\n"
            f"1. Click this link: {short_url}\n"
            "2. Complete the steps on the site.\n"
            "3. You will be redirected back here.\n"
            "4. Click 'Start' to finish verification.\n\n"
            f"📺 **Need help?** [Watch Tutorial Video]({HOW_TO_VERIFY_VIDEO_URL})\n\n"
            "Once verified, you will have 12 hours of uninterrupted access! 🎬",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return
    
    # Get remaining hours for re-verification
    hours_remaining = get_hours_until_revert(user_id)
    
    db = load_db()
    
    results = []
    # Find all movies where the query is part of the title
    for movie in db:
        if query in movie["title_lower"]:
            results.append(movie)
            
    if not results:
        bot.reply_to(message, "😔 **Movie not found!**\n\nPlease check the spelling or search for another movie.", parse_mode="Markdown")
        return
    
    # Show verification status
    status_msg = f"🔍 Found {len(results)} result(s)! Sending them now... 🍿\n\n⏱️ *Your verification expires in {hours_remaining:.1f} hours*"
    bot.reply_to(message, status_msg, parse_mode="Markdown")
    
    # Send up to 3 results to prevent spamming
    count = 0
    for result_movie in results:
        if count >= 3:
            bot.send_message(message.chat.id, "*(Showing max 3 results to prevent spam)*", parse_mode="Markdown")
            break
            
        file_id = result_movie["file_id"]
        title = result_movie["title"]
        file_type = result_movie["type"]
        
        caption = f"🎬 {title}\n\n🍿 Provided by MovieWorld"
        
        try:
            if file_type == "video":
                bot.send_video(chat_id=message.chat.id, video=file_id, caption=caption)
            else:
                bot.send_document(chat_id=message.chat.id, document=file_id, caption=caption)
        except Exception as e:
            # Maybe the file was deleted by Telegram
            pass
        count += 1

print("Starting Auto-Search Movie Bot...")
if __name__ == "__main__":
    # Start the Flask web server in a separate thread so Render doesn't crash the bot
    server_thread = threading.Thread(target=run_server)
    server_thread.start()
    
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=True)
    except Exception as e:
        print(f"Bot polling stopped with error: {e}")
