import os
import json
import threading
from datetime import datetime
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
import asyncio

# ---------- CONFIG ----------
GOOGLE_SHEET_NAME = "ParkingBot Data"
GOOGLE_FORM_LINK = "https://docs.google.com/forms/d/e/1FAIpQLScPJ8EXzwmKnsQxv0vunid4SZy_JUo98ewvr-_eZhSLdUI2kw/viewform"

# ---------- Flask App ----------
app = Flask(__name__)

# ---------- Google Sheets Setup ----------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

creds_json = os.environ.get("GOOGLE_CREDS_JSON")
if not creds_json:
    raise Exception("❌ GOOGLE_CREDS_JSON environment variable not set!")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)

ss = gc.open(GOOGLE_SHEET_NAME)
db_ws = ss.worksheet("database")
reg_ws = ss.worksheet("registration")
logs_ws = ss.worksheet("logs")

# ---------- HELPER FUNCTIONS ----------
def find_db_by_uid(uid):
    records = db_ws.get_all_records()
    return next((r for r in records if str(r.get("uid")) == str(uid)), None)

def find_reg_by_student(student_number):
    records = reg_ws.get_all_records()
    return next((r for r in records if str(r.get("Student Number")) == str(student_number)), None)

def count_motos_inside(student_number):
    rows = logs_ws.get_all_records()
    ins = sum(1 for r in rows if str(r.get("student_number")) == str(student_number) and r.get("direction") == "IN")
    outs = sum(1 for r in rows if str(r.get("student_number")) == str(student_number) and r.get("direction") == "OUT")
    return max(0, ins - outs)

# ---------- Flask Endpoint ----------
@app.route("/rfid_tap", methods=["POST"])
def rfid_tap():
    data = request.get_json(force=True)
    uid = data.get("uid")
    direction = data.get("direction", "IN").upper()
    if not uid:
        return jsonify({"status": "error", "signal": "RED", "message": "No UID"}), 400

    if direction not in ("IN", "OUT"):
        direction = "IN"

    db_entry = find_db_by_uid(uid)
    if not db_entry:
        return jsonify({"status": "denied", "signal": "RED", "message": "UID not found in database"}), 403

    name = db_entry.get("name", "Unknown")
    student_number = db_entry.get("student_number", "")

    reg = find_reg_by_student(student_number)
    plates = reg.get("Plates") if reg else "N/A"
    try:
        num_motos = int(reg.get("Number of Motorcycles")) if reg else 1
    except:
        num_motos = 1

    motos_before = count_motos_inside(student_number)
    motos_after = motos_before + 1 if direction == "IN" else max(0, motos_before - 1)
    motos_left = max(0, num_motos - motos_after)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logs_ws.append_row([uid, name, student_number, plates, direction, timestamp, motos_after, motos_left])

    # Telegram notify
    telegram_id = reg.get("Telegram ID") if reg else None
    if telegram_id and hasattr(app, "bot_app"):
        msg = (
            f"✅ {direction} recorded\n"
            f"Name: {name}\n"
            f"Student #: {student_number}\n"
            f"Plates: {plates}\n"
            f"Motos inside: {motos_after}\n"
            f"Motos left: {motos_left}\n"
            f"Time: {timestamp}"
        )
        try:
            asyncio.run_coroutine_threadsafe(
                app.bot_app.bot.send_message(chat_id=int(telegram_id), text=msg),
                app.bot_loop
            )
        except Exception as e:
            print("Telegram send error:", e)

    return jsonify({
        "status": "granted",
        "signal": "GREEN",
        "name": name,
        "student_number": student_number,
        "plates": plates,
        "direction": direction,
        "timestamp": timestamp,
        "motos_in": motos_after,
        "motos_left": motos_left
    }), 200

# ---------- Telegram Bot ----------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! Use /register to sign up.")

async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚗 ParkingBot logs motorcycle parking and notifies you.")

async def register_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📝 Register here: {GOOGLE_FORM_LINK}")

def run_bot():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise Exception("❌ BOT_TOKEN not set!")

    async def main():
        bot_app = Application.builder().token(token).build()
        bot_app.add_handler(CommandHandler("start", start_cmd))
        bot_app.add_handler(CommandHandler("about", about_cmd))
        bot_app.add_handler(CommandHandler("register", register_cmd))

        app.bot_app = bot_app
        app.bot_loop = asyncio.get_event_loop()

        print("🚀 Telegram bot is starting polling...")
        await bot_app.run_polling()

    asyncio.run(main())

# Start bot in background thread
threading.Thread(target=run_bot, daemon=True).start()

# ---------- Entrypoint ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
