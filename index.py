import os
import time
import json
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Environment se tokens uthana
TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")
ADMIN_ID = 1238405133  # Aapka Admin Telegram ID

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set!")

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

REQUIRED_CHATS = ['@studenthelpclub', '@studenthelpclubofficial'] 
FINAL_GROUP_LINK = "https://t.me/+YwUmMpjCgHFkZDdl"
YOUTUBE_CHANNEL_LINK = "https://www.youtube.com/@vishalhelpclub"

ASSIGNMENT_WEBSITE = "https://studenthelpclub.in" 
JOBS_WEBSITE = "https://jobs.studenthelpclub.in"
UTILITY_TOOLS = "https://shctools.in/"

# Aapka QR Code Direct Image Link
QR_CODE_URL = "https://raw.githubusercontent.com/studenthelpclub/files/main/qrcode.jpg"

WAITING_FOR_ENROLLMENT = set()
WAITING_FOR_COURSE = set()

# --- GOOGLE SHEETS SETUP ---
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    user_doc = client.open("Student Help Club Data")
    users_sheet = user_doc.worksheet("Users")

    master_doc = client.open("Master Sheet")
    sheet1 = master_doc.worksheet("Sheet1")
    sheet4 = master_doc.worksheet("Sheet4")
except Exception as e:
    print(f"Google Sheets Connection Error: {e}")

def save_user(message, mobile="N/A"):
    try:
        user_id = str(message.from_user.id)
        existing_users = users_sheet.col_values(1)
        if user_id not in existing_users:
            name = message.from_user.first_name or "N/A"
            username = message.from_user.username or "N/A"
            users_sheet.append_row([user_id, name, username, mobile])
    except Exception as e:
        print(f"Error saving user: {e}")

def check_membership(user_id):
    for chat_id in REQUIRED_CHATS:
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

def get_main_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    btn_result = InlineKeyboardButton("🔍 Check IGNOU Result", callback_data="start_check_result")
    btn_assignment = InlineKeyboardButton("📖 Get Solved Assignment PDF", callback_data="start_assignment")
    btn_group = InlineKeyboardButton("📚 Join Solved Assignments Group", url=FINAL_GROUP_LINK)
    btn_website = InlineKeyboardButton("🌐 Visit Official Website", url=ASSIGNMENT_WEBSITE)
    btn_jobs = InlineKeyboardButton("💼 Latest Job Updates", url=JOBS_WEBSITE)
    btn_tools = InlineKeyboardButton("🛠️ Student Utility Tools", url=UTILITY_TOOLS)
    markup.add(btn_result, btn_assignment, btn_group, btn_website, btn_jobs, btn_tools)
    return markup

def send_join_message(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📢 Join Main Channel", url="https://t.me/studenthelpclub"))
    markup.add(InlineKeyboardButton("👥 Join Discussion Group", url="https://t.me/studenthelpclubofficial"))
    markup.add(InlineKeyboardButton("✅ I Have Joined (Verify)", callback_data="verify_join"))
    
    join_msg = (
        "👋 <b>Welcome to Student Help Club Official Bot!</b>\n\n"
        "📚 IGNOU ke sabhi Solved Assignments, Academic Updates, aur Jobs ki jankari prapt karne ke liye, "
        "kripya hamare official channels ko join karein.\n\n"
        "👇 <i>Neeche diye gaye buttons par click karke join karein aur '✅ I Have Joined' par click karein.</i>"
    )
    bot.send_message(chat_id, join_msg, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['start', 'restart'])
def send_welcome(message):
    save_user(message)
    user_id = message.from_user.id
    if check_membership(user_id):
        welcome_text = (
            "🌟 <b>Welcome Back to Student Help Club Portal!</b>\n\n"
            "Aapke sabhi academic solutions ke liye ek hi platform. "
            "Kripya niche diye gaye options mein se apni zaroorat ke anusaar select karein:"
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode='HTML', reply_markup=get_main_menu())
    else:
        send_join_message(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_callback(call):
    user_id = call.from_user.id
    save_user(call.message)
    
    if check_membership(user_id):
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass 
            
        success_msg = (
            "✅ <b>Verification Successful!</b>\n\n"
            "Dhanyawad! Ab aap Student Help Club ke verified member hain. 🎉\n\n"
            "👇 <i>Apni service select karne ke liye niche click karein:</i>"
        )
        bot.send_message(call.message.chat.id, success_msg, parse_mode='HTML', reply_markup=get_main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ Kripya pehle dono channels join karein!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "start_check_result")
def prompt_enrollment(call):
    user_id = call.from_user.id
    if not check_membership(user_id):
        bot.answer_callback_query(call.id, "❌ Kripya pehle channels join karein!", show_alert=True)
        send_join_message(call.message.chat.id)
        return
    
    WAITING_FOR_ENROLLMENT.add(user_id)
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id, 
        "📝 <b>IGNOU Result Portal</b>\n\nKripya apna 10-digit <b>Enrollment Number</b> yahan type karke bhejein:", 
        parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data == "start_assignment")
def prompt_course_code(call):
    user_id = call.from_user.id
    if not check_membership(user_id):
        bot.answer_callback_query(call.id, "❌ Kripya pehle channels join karein!", show_alert=True)
        send_join_message(call.message.chat.id)
        return
    
    WAITING_FOR_COURSE.add(user_id)
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id, 
        "📖 <b>IGNOU Solved Assignment Portal</b>\n\nKripya apna <b>Course Code</b> yahan type karke bhejein (Example: <code>BPSC 110</code> ya <code>BCOC 134</code>):", 
        parse_mode='HTML'
    )

# Broadcast Command
@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Aapko yeh command use karne ki permission nahi hai.")
        return
    
    msg_to_broadcast = message.text.replace("/broadcast", "").strip()
    if not msg_to_broadcast:
        bot.reply_to(message, "⚠️ Kripya message likhein. Format: `/broadcast [Aapka Message]`", parse_mode="Markdown")
        return

    try:
        users = users_sheet.col_values(1)
        success, fail = 0, 0
        bot.reply_to(message, "📢 Broadcast transmission started...")
        for uid in users:
            if uid.isdigit():
                try:
                    bot.send_message(chat_id=int(uid), text=msg_to_broadcast, parse_mode='HTML')
                    success += 1
                    time.sleep(0.1)
                except Exception:
                    fail += 1
        bot.send_message(message.chat.id, f"✅ <b>Broadcast Report:</b>\n\n• Successfully Sent: {success}\n• Failed: {fail}", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ Broadcast Error: {e}")

def fetch_ignou_result(enr_no, chat_id):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    driver.set_page_load_timeout(60)

    url = "https://termendresult.ignou.ac.in/login.aspx"
    file_name = f"Student_Help_Club_Result_{enr_no}.png"
    success = False

    while not success:
        try:
            driver.get(url)
            wait = WebDriverWait(driver, 20)
            ddl_result_type = wait.until(EC.presence_of_element_located((By.ID, "ddlresultype")))
            Select(ddl_result_type).select_by_index(1)
            time.sleep(3)
            driver.find_element(By.ID, "txtEnrno").send_keys(enr_no)
            driver.find_element(By.ID, "btnlogin").click()
            time.sleep(5)
            
            if "Marks/Grade" in driver.page_source or "view_gradecard.aspx" in driver.current_url:
                total_height = driver.execute_script("return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);")
                driver.set_window_size(1920, total_height + 100)
                time.sleep(1)
                driver.save_screenshot(file_name)
                success = True
            else:
                time.sleep(3)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
    driver.quit()

    if success and os.path.exists(file_name):
        caption_text = f"✅ <b>Result for Enrollment:</b> <code>{enr_no}</code>\n\n🚀 <i>Powered by Student Help Club</i>"
        with open(file_name, 'rb') as photo:
            bot.send_photo(chat_id, photo=photo, caption=caption_text, parse_mode="HTML")
        os.remove(file_name)
    else:
        bot.send_message(chat_id, "❌ Server temporary down hai. Kripya kuch samay baad punah prayas karein.")

def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

# Paid / Free Choice Handler with Professional Button Layout
@bot.callback_query_handler(func=lambda call: call.data.startswith("paid_") or call.data.startswith("free_"))
def handle_assignment_choice(call):
    data_parts = call.data.split('_', 1)
    choice = data_parts[0]
    search_term = data_parts[1]
    
    if choice == "paid":
        try:
            # QR Code bhejna aur professional message ke sath
            sent_msg = bot.send_photo(
                call.message.chat.id, 
                photo=QR_CODE_URL, 
                caption=(
                    "💳 <b>Secure Payment Gateway - Student Help Club</b>\n\n"
                    "• <b>Assignment PDF Price:</b> <ant_t>₹20</ant_t> (Special Discounted Rate)\n\n"
                    "📌 <i>Instructions:</i>\n"
                    "1. Upar diye gaye QR Code ko scan karke <b>₹20</b> pay karein.\n"
                    "2. Payment successful hone ke baad <b>Screenshot</b> yahan chat mein upload karein.\n"
                    "3. Verification ke turant baad aapko PDF file provide kar di jayegi.\n\n"
                    "⚠️ <i>Security Notice: Yeh QR code message kuch samay mein automatically expire/delete ho sakta hai.</i>"
                ),
                parse_mode='HTML'
            )
            
            # Optional: 2 minute (120 seconds) ke baad QR code message ko automatic delete karne ke liye background thread ya logic laga sakte hain
        except Exception:
            bot.send_message(call.message.chat.id, "❌ QR Code load hone mein samasya aayi. Kripya admin se sampark karein.", parse_mode='HTML')
        
    elif choice == "free":
        try:
            records_sheet4 = sheet4.get_all_values()
            yt_link = YOUTUBE_CHANNEL_LINK
            for row in records_sheet4:
                if len(row) > 3:
                    sheet4_course_name = str(row[0]).upper().replace(" ", "").replace("-", "")
                    if search_term in sheet4_course_name:
                        if row[3].strip() != "":
                            yt_link = row[3]
                        break
        except Exception:
            yt_link = YOUTUBE_CHANNEL_LINK

        # Professional Buttons for Free Options (Jaisa aapne image mein manga hai)
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📢 Join Telegram Assignment Group", url=FINAL_GROUP_LINK),
            InlineKeyboardButton("📺 Watch & Write via YouTube Video", url=yt_link)
        )

        reply = (
            "🆓 <b>Free IGNOU Solved Assignment Access</b>\n\n"
            "Aap bilkul nishulk (Free) mein hamare resources ka upyog karke apna assignment likh sakte hain:\n\n"
            "👇 <i>Neeche diye gaye buttons par click karke group join karein ya video dekhein:</i>"
        )
        bot.send_message(call.message.chat.id, reply, parse_mode='HTML', reply_markup=markup)

@bot.message_handler(func=lambda message: True, content_types=['text', 'audio', 'document', 'photo', 'sticker', 'video', 'video_note', 'voice', 'location', 'contact'])
def continuous_check(message):
    user_id = message.from_user.id
    chat_type = message.chat.type
    
    if chat_type in ['group', 'supergroup']:
        if is_admin(message.chat.id, user_id):
            return
        if not check_membership(user_id):
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass
            return 
        if message.content_type == 'document':
            return 
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
            
    elif chat_type == 'private':
        if not check_membership(user_id):
             send_join_message(message.chat.id)
        else:
            if message.content_type == 'text' and not message.text.startswith('/'):
                if user_id in WAITING_FOR_ENROLLMENT:
                    WAITING_FOR_ENROLLMENT.remove(user_id)
                    enr_number = message.text.strip()
                    bot.send_message(message.chat.id, f"🔍 <b>Enrollment Number ({enr_number}) received!</b>\n\nSystem result fetch kar raha hai, kripya prateeksha karein...", parse_mode='HTML', reply_markup=get_main_menu())
                    fetch_ignou_result(enr_number, message.chat.id)
                
                elif user_id in WAITING_FOR_COURSE:
                    WAITING_FOR_COURSE.remove(user_id)
                    text = message.text.strip().upper()
                    search_term = text.replace(" ", "").replace("-", "")
                    
                    try:
                        records_sheet1 = sheet1.get_all_values()
                        exact_name = None
                        for row in records_sheet1:
                            if len(row) > 0:
                                sheet_course_name = str(row[0]).upper().replace(" ", "").replace("-", "")
                                if search_term in sheet_course_name:
                                    exact_name = row[0]
                                    break
                        
                        if exact_name:
                            markup = InlineKeyboardMarkup(row_width=2)
                            markup.add(InlineKeyboardButton("💰 Paid PDF (₹20)", callback_data=f"paid_{search_term}"),
                                       InlineKeyboardButton("🆓 Free YouTube", callback_data=f"free_{search_term}"))
                            
                            reply_text = (
                                f"✅ <b>Course Found:</b> <code>{exact_name}</code>\n\n"
                                "Hamare paas is assignment ke do options available hain:\n"
                                "• **Paid Option:** Sirf ₹20 mein instant high-quality PDF prapt karein.\n"
                                "• **Free Option:** YouTube video aur Telegram group ke madhyam se bilkul free likhein.\n\n"
                                "👇 <i>Kripya apna pasandeeda option select karein:</i>"
                            )
                            bot.send_message(message.chat.id, reply_text, parse_mode='HTML', reply_markup=markup)
                        else:
                            bot.send_message(message.chat.id, f"❌ Maaf kijiyega, <b>{text}</b> ka assignment abhi database mein available nahi hai.", parse_mode='HTML')
                    except Exception as e:
                        bot.send_message(message.chat.id, f"❌ Error: {e}")
                else:
                     bot.send_message(message.chat.id, "👇 Kripya niche diye gaye menu se apna vikalp chunein:", parse_mode='HTML', reply_markup=get_main_menu())

@app.route('/', methods=['GET', 'POST'])
@app.route('/api/index', methods=['GET', 'POST'])
def index():
    if request.content_type == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Student Help Club Bot is active and running 24/7!', 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
