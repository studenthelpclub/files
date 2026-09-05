import os
import time
import json
import re
import threading
import requests
import io
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader, PdfWriter
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

TOKEN = os.environ.get("TELEGRAM_TOKEN")
GOOGLE_CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS")
ADMIN_ID = 1238405133  # Aapka Admin Telegram ID

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set!")

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# --- CHANNELS & LINKS ---
REQUIRED_CHATS = ['@studenthelpclub', '@studenthelpclubofficial'] 

YT_POST_DESTINATIONS = [
    '@studenthelpclubofficial',  # Main Chat Group
    '@studenthelpclub',          # Main Channel
    -1004353231367               # IGNOU Solved Group (Numeric ID)
]

AUTO_ALERT_CHANNEL = '@studenthelpclub'

FINAL_GROUP_LINK = "https://t.me/+YwUmMpjCgHFkZDdl"
YOUTUBE_CHANNEL_LINK = "https://www.youtube.com/@vishalhelpclub?sub_confirmation=1"
ADMIN_USERNAME_LINK = "https://t.me/studenthelpclub1"

ASSIGNMENT_WEBSITE = "https://studenthelpclub.in" 
JOBS_WEBSITE = "https://jobs.studenthelpclub.in"
UTILITY_TOOLS = "https://shctools.in/"

QR_CODE_URL = "https://raw.githubusercontent.com/studenthelpclub/files/main/qrcode.jpg"
UPI_ID = "studenthelpclub@naviaxis"
PRICE_PER_PDF = 20  
POINTS_PER_REFERRAL = 5  # Ek referral par milne wale points

# --- STATE VARIABLES ---
WAITING_FOR_ENROLLMENT = set()
WAITING_FOR_COURSE = set()
USER_STATE = {}

POSTED_YT_LINKS = set()
LAST_IGNOU_ALERT = ""

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

# ==========================================
# 🛠️ HELPER FUNCTIONS (REFERRAL & POINTS)
# ==========================================
def clean_string(text):
    return re.sub(r'[^A-Z0-9]', '', str(text).upper())

def get_direct_drive_url(drive_url):
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', drive_url)
    if not match:
        match = re.search(r'id=([a-zA-Z0-9-_]+)', drive_url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&confirm=t&id={file_id}"
    return None

def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

def get_user_row(user_id_str):
    try:
        cell = users_sheet.find(user_id_str)
        if cell:
            return cell.row
    except Exception:
        pass
    return None

def get_user_points(user_id_str):
    try:
        row = get_user_row(user_id_str)
        if row:
            val = users_sheet.cell(row, 5).value  # Column 5: Points
            return int(val) if val and val.isdigit() else 0
    except Exception:
        pass
    return 0

def update_user_points(user_id_str, points):
    try:
        row = get_user_row(user_id_str)
        if row:
            users_sheet.update_cell(row, 5, str(points))
    except Exception:
        pass

def save_user(message, referrer_id=None):
    try:
        user_id = str(message.from_user.id)
        col_vals = users_sheet.col_values(1)
        if user_id not in col_vals:
            name = message.from_user.first_name or "N/A"
            username = message.from_user.username or "N/A"
            ref_by = str(referrer_id) if referrer_id and referrer_id != user_id else "None"
            users_sheet.append_row([user_id, name, username, "N/A", "0", ref_by])
            
            if referrer_id and referrer_id != user_id:
                ref_row = get_user_row(str(referrer_id))
                if ref_row:
                    current_pts = get_user_points(str(referrer_id))
                    new_pts = current_pts + POINTS_PER_REFERRAL
                    update_user_points(str(referrer_id), new_pts)
                    try:
                        bot.send_message(
                            int(referrer_id),
                            f"🎉 <b>Referral Bonus Credited!</b>\n\nNaye student ne aapke link se join kiya hai. Aapke account mein <b>+{POINTS_PER_REFERRAL} Points</b> add kar diye gaye hain! 🎁",
                            parse_mode='HTML'
                        )
                    except:
                        pass
    except Exception as e:
        print(f"Save user error: {e}")

def check_membership(user_id):
    for chat_id in REQUIRED_CHATS:
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

# ==========================================
# 🚀 ADMIN COMMANDS (/chatid, /post_yt, /broadcast)
# ==========================================
@bot.message_handler(commands=['chatid'])
def handle_chatid(message):
    bot.reply_to(message, f"📌 <b>This Chat ID is:</b> <code>{message.chat.id}</code>", parse_mode='HTML')

@bot.message_handler(commands=['post_yt'])
def manual_post_youtube(message):
    if message.from_user.id != ADMIN_ID: return
    bot.reply_to(message, "⏳ <i>Scanning Sheet 4 for the latest YouTube Link...</i>", parse_mode='HTML')
    try:
        records_4 = sheet4.get_all_values()
        found_row = None
        for row in records_4[1:]:
            if len(row) > 3 and "youtu" in str(row[3]).lower():
                found_row = row
                break
                
        if found_row:
            subject_code = str(found_row[0]).strip().upper()
            yt_link = str(found_row[3]).strip()
            
            yt_msg = (
                "🎓 <b>PREMIUM SOLVED ASSIGNMENT RELEASED</b> 🎓\n\n"
                "Dear Students,\n"
                "A new fully solved assignment tutorial has been uploaded for your academic preparation.\n\n"
                f"📖 <b>Subject Code:</b> <code>{subject_code}</code>\n\n"
                "Watch the complete tutorial to prepare your assignments perfectly and absolutely free of cost! 💯\n\n"
                f"📺 <b>Watch Full Video Here:</b>\n👉 {yt_link}\n\n"
                "💡 <i>If you found this helpful, please <b>Like</b> the video, <b>Subscribe</b> to our channel, and let us know your next Subject Code in the comments!</i>"
            )
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("📺 Watch & Prepare Now", url=yt_link),
                InlineKeyboardButton("🔔 Subscribe for Updates", url=YOUTUBE_CHANNEL_LINK)
            )
            
            success_count = 0
            for dest in YT_POST_DESTINATIONS:
                try:
                    bot.send_message(dest, yt_msg, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=False)
                    success_count += 1
                except Exception: pass
                    
            bot.send_message(message.chat.id, f"✅ <b>Success!</b> Broadcasted to {success_count} groups/channels.", parse_mode='HTML')
            POSTED_YT_LINKS.add(yt_link)
        else:
            bot.send_message(message.chat.id, "❌ Error: No valid YouTube link found.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Failed to post: {e}")

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.id != ADMIN_ID: return
    msg_to_broadcast = message.text.replace("/broadcast", "").strip()
    if not msg_to_broadcast:
        bot.reply_to(message, "⚠️ Format: `/broadcast [Message]`")
        return
    try:
        users = users_sheet.col_values(1)
        success, fail = 0, 0
        bot.reply_to(message, "📢 Broadcast initiated...")
        for uid in users:
            if uid.isdigit():
                try:
                    bot.send_message(chat_id=int(uid), text=msg_to_broadcast, parse_mode='HTML')
                    success += 1
                    time.sleep(0.1)
                except Exception:
                    fail += 1
        bot.send_message(message.chat.id, f"✅ <b>Broadcast Complete:</b>\nSent: {success}\nFailed: {fail}", parse_mode='HTML')
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Broadcast Error: {e}")

# ==========================================
# 🚀 BACKGROUND AUTO-TASKS
# ==========================================
def background_auto_tasks():
    global POSTED_YT_LINKS, LAST_IGNOU_ALERT
    try:
        records = sheet4.get_all_values()
        for row in records:
            if len(row) > 3 and "youtu" in str(row[3]).lower():
                POSTED_YT_LINKS.add(str(row[3]).strip())
    except Exception: pass

    while True:
        try:
            records_4 = sheet4.get_all_values()
            for row in records_4[1:]:
                if len(row) > 3:
                    yt_link = str(row[3]).strip()
                    if yt_link != "" and "youtu" in yt_link.lower() and yt_link not in POSTED_YT_LINKS:
                        subject_code = str(row[0]).strip().upper()
                        
                        yt_msg = (
                            "🎓 <b>PREMIUM SOLVED ASSIGNMENT RELEASED</b> 🎓\n\n"
                            "Dear Students,\n"
                            "A new fully solved assignment tutorial has been uploaded for your academic preparation.\n\n"
                            f"📖 <b>Subject Code:</b> <code>{subject_code}</code>\n\n"
                            "Watch the complete tutorial to prepare your assignments perfectly and absolutely free of cost! 💯\n\n"
                            f"📺 <b>Watch Full Video Here:</b>\n👉 {yt_link}\n\n"
                            "💡 <i>If you found this helpful, please <b>Like</b> the video, <b>Subscribe</b> to our channel, and let us know your next Subject Code in the comments!</i>"
                        )
                        markup = InlineKeyboardMarkup(row_width=1)
                        markup.add(
                            InlineKeyboardButton("📺 Watch & Prepare Now", url=yt_link),
                            InlineKeyboardButton("🔔 Subscribe for Updates", url=YOUTUBE_CHANNEL_LINK)
                        )
                        for dest in YT_POST_DESTINATIONS:
                            try: bot.send_message(dest, yt_msg, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=False)
                            except Exception: pass
                        POSTED_YT_LINKS.add(yt_link)

            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get("http://www.ignou.ac.in/ignou/bulletinboard/announcements/latest/1", headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                first_alert = soup.find('div', class_='usercontent').find('a')
                if first_alert:
                    alert_text = first_alert.text.strip()
                    alert_link = first_alert['href']
                    if not alert_link.startswith("http"):
                        alert_link = "http://www.ignou.ac.in" + alert_link

                    if LAST_IGNOU_ALERT == "":
                        LAST_IGNOU_ALERT = alert_text
                    elif alert_text != LAST_IGNOU_ALERT:
                        alert_msg = (
                            "📢 <b>IGNOU LATEST OFFICIAL NOTIFICATION</b> 📢\n\n"
                            f"📌 <b>Update:</b> {alert_text}\n\n"
                            "🔗 <b>Official Details Link:</b>\n"
                            f"👉 <a href='{alert_link}'>Click Here to Read More</a>\n\n"
                            "<i>Stay updated with Student Help Club!</i>"
                        )
                        bot.send_message(AUTO_ALERT_CHANNEL, alert_msg, parse_mode='HTML', disable_web_page_preview=True)
                        LAST_IGNOU_ALERT = alert_text
            except Exception: pass
        except Exception: pass
        time.sleep(1800)

bg_thread = threading.Thread(target=background_auto_tasks, daemon=True)
bg_thread.start()

# ==========================================
# 📱 MENUS & NAVIGATION (BACK VS MAIN MENU FIX)
# ==========================================
def get_main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 IGNOU Result", callback_data="start_check_result"),
        InlineKeyboardButton("📖 Order PDF Assignment", callback_data="start_assignment"),
        InlineKeyboardButton("🎁 Refer & Earn", callback_data="refer_earn"),
        InlineKeyboardButton("📚 Join Academic Group", url=FINAL_GROUP_LINK),
        InlineKeyboardButton("🌐 Visit Official Website", url=ASSIGNMENT_WEBSITE),
        InlineKeyboardButton("💼 Latest Job Updates", url=JOBS_WEBSITE),
        InlineKeyboardButton("🛠️ Useful Student Tools", url=UTILITY_TOOLS)
    )
    return markup

def get_navigation_buttons(back_callback):
    """Separate Back and Main Menu buttons for clean navigation"""
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⬅️ Back", callback_data=back_callback),
        InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
    )
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def handle_back(call):
    user_id = call.from_user.id
    WAITING_FOR_ENROLLMENT.discard(user_id)
    WAITING_FOR_COURSE.discard(user_id)
    if user_id in USER_STATE:
        del USER_STATE[user_id]
        
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except: pass
    bot.send_message(call.message.chat.id, "👇 <b>Main Dashboard:</b>\nPlease select an option from the menu below to proceed:", parse_mode='HTML', reply_markup=get_main_menu())

def send_join_message(chat_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📢 Join Main Channel", url="https://t.me/studenthelpclub"))
    markup.add(InlineKeyboardButton("👥 Join Discussion Group", url="https://t.me/studenthelpclubofficial"))
    markup.add(InlineKeyboardButton("✅ I Have Joined (Verify)", callback_data="verify_join"))
    
    join_msg = (
        "👋 <b>Welcome to Student Help Club Official Portal!</b>\n\n"
        "To access IGNOU Solved Assignments, Academic Alerts, and Premium Services, please join our official communities.\n\n"
        "👇 <i>Click the buttons below to join, then click 'I Have Joined' to verify your status.</i>"
    )
    bot.send_message(chat_id, join_msg, reply_markup=markup, parse_mode='HTML')

@bot.message_handler(commands=['start', 'restart'])
def send_welcome(message):
    user_id = message.from_user.id
    text = message.text
    referrer_id = None
    
    if "ref_" in text:
        try:
            parts = text.split("ref_")
            if len(parts) > 1:
                referrer_id = parts[1].strip()
        except:
            pass

    save_user(message, referrer_id=referrer_id)

    if check_membership(user_id):
        welcome_text = (
            "🎓 <b>Welcome to Student Help Club Premium Bot!</b>\n\n"
            "Your ultimate destination for IGNOU Academic Solutions. We provide verified solved assignments, instant results, and career updates.\n\n"
            "Please select your required service from the menu below:"
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode='HTML', reply_markup=get_main_menu())
    else:
        send_join_message(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == "refer_earn")
def handle_refer_earn(call):
    user_id = call.from_user.id
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except: pass
    
    bot_info = bot.get_me()
    bot_username = bot_info.username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    user_pts = get_user_points(str(user_id))
    
    refer_msg = (
        "🎁 <b>Student Help Club - Refer & Earn Program</b>\n\n"
        "Apne doston aur classmates ko invite karein aur har successful join par reward points paayein!\n\n"
        f"💰 <b>Per Referral Bonus:</b> +{POINTS_PER_REFERRAL} Points\n"
        f"⭐ <b>Aapke Total Points:</b> <b>{user_pts} Points</b> (₹{user_pts} Discount Value)\n\n"
        "🔗 <b>Aapka Unique Referral Link:</b>\n"
        f"<code>{referral_link}</code>\n\n"
        "📌 <i>Jab bhi koi dost is link se bot start karega, aapke account mein points jud jayenge. In points ko aap assignment kharidte waqt discount ke roop mein use kar sakte hain!</i>"
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📤 Share Link with Friends", url=f"https://t.me/share/url?url={referral_link}&text=📚%20IGNOU%20ke%20sabhi%20Solved%20Assignments%20aur%20Updates%20ke%20liye%20yeh%20Bot%20join%20karein!"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
    )
    bot.send_message(user_id, refer_msg, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_callback(call):
    user_id = call.from_user.id
    save_user(call.message)
    if check_membership(user_id):
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception: pass 
        bot.send_message(call.message.chat.id, "✅ <b>Access Verified!</b>\n\nThank you for joining our community. 🎉\n👇 <i>Please choose a service from the dashboard:</i>", parse_mode='HTML', reply_markup=get_main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ Please ensure you have joined both channels before verifying!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "start_check_result")
def prompt_enrollment(call):
    user_id = call.from_user.id
    if not check_membership(user_id):
        bot.answer_callback_query(call.id, "❌ Access Denied! Please join our channels first.", show_alert=True)
        return
    WAITING_FOR_ENROLLMENT.add(user_id)
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except: pass
    bot.send_message(call.message.chat.id, "🎓 <b>IGNOU Result Portal</b>\n\nWelcome to the official result checking system.\n\nPlease enter your 9 or 10-digit <b>Enrollment Number</b> below:", parse_mode='HTML', reply_markup=get_navigation_buttons("back_to_main"))

@bot.callback_query_handler(func=lambda call: call.data == "start_assignment")
def prompt_course_code(call):
    user_id = call.from_user.id
    if not check_membership(user_id):
        bot.answer_callback_query(call.id, "❌ Access Denied! Please join our channels first.", show_alert=True)
        return
    WAITING_FOR_COURSE.add(user_id)
    try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except: pass
    instruction_msg = (
        "📚 <b>Premium Solved Assignment Delivery</b>\n\n"
        "Please enter your required <b>Course Code(s)</b> below to check availability.\n\n"
        "📌 <i>Pro Tip: To order multiple subjects at once, separate them with commas (e.g., BPSC 110, BCOC 134, BHIC 132).</i>"
    )
    bot.send_message(call.message.chat.id, instruction_msg, parse_mode='HTML', reply_markup=get_navigation_buttons("back_to_main"))

# ==========================================
# 📝 IGNOU RESULT FETCHING
# ==========================================
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
        except Exception:
            time.sleep(5)
    driver.quit()

    if success and os.path.exists(file_name):
        caption_text = (
            f"✅ <b>Result Generated for Enrollment:</b> <code>{enr_no}</code>\n\n"
            f"🚀 <i>Service Powered by:</i> <b>Student Help Club</b>\n"
            f"📢 <b>Official Channel:</b> @studenthelpclub\n"
            f"🌐 <b>Website:</b> studenthelpclub.in"
        )
        with open(file_name, 'rb') as photo:
            bot.send_photo(chat_id, photo=photo, caption=caption_text, parse_mode="HTML")
        os.remove(file_name)
    else:
        bot.send_message(chat_id, "⚠️ We are currently unable to connect to the IGNOU servers due to high traffic. Please try again later.")

# ==========================================
# 🔀 CALLBACK HANDLERS (FLOW LOGIC & ADMIN FIX)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith("set_med_") or call.data in ["choice_paid", "choice_free", "admin_verify", "admin_reject", "view_sample", "redeem_points", "back_to_assignment"])
def handle_flow(call):
    user_id = call.message.chat.id
    
    if call.data == "back_to_assignment":
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except: pass
        WAITING_FOR_COURSE.add(user_id)
        instruction_msg = (
            "📚 <b>Premium Solved Assignment Delivery</b>\n\n"
            "Please enter your required <b>Course Code(s)</b> below to check availability.\n\n"
            "📌 <i>Pro Tip: To order multiple subjects at once, separate them with commas (e.g., BPSC 110, BCOC 134, BHIC 132).</i>"
        )
        bot.send_message(user_id, instruction_msg, parse_mode='HTML', reply_markup=get_navigation_buttons("back_to_main"))
        return

    if call.data == "admin_reject":
        if call.from_user.id != ADMIN_ID: return
        caption = call.message.caption
        if not caption: return
            
        user_id_match = re.search(r"System ID:\s*<code>(\d+)<\/code>", caption)
        if not user_id_match:
            user_id_match = re.search(r"UserID:\s*(\d+)", caption)
        if not user_id_match: return
            
        target_uid = int(user_id_match.group(1))
        reject_msg = (
            "⚠️ <b>Payment Verification Unsuccessful</b>\n\n"
            "Dear Student,\nWe could not verify the payment screenshot you provided. It appears to be invalid or incomplete, and your PDF delivery has been paused.\n\n"
            "If the amount has been successfully deducted from your bank account, please upload a clear, correct receipt or contact our support desk immediately for manual assistance:\n"
            f"👉 <b>{ADMIN_USERNAME_LINK}</b>"
        )
        reject_markup = InlineKeyboardMarkup(row_width=1)
        reject_markup.add(
            InlineKeyboardButton("🎧 Contact Admin Support", url=ADMIN_USERNAME_LINK),
            InlineKeyboardButton("🔙 Return to Main Menu", callback_data="back_to_main")
        )
        try:
            bot.send_message(target_uid, reject_msg, parse_mode='HTML', disable_web_page_preview=True, reply_markup=reject_markup)
            bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=caption + "\n\n<b>[STATUS: DECLINED ❌]</b>", parse_mode='HTML')
        except Exception: pass
        bot.answer_callback_query(call.id, "Payment Rejected and User Notified!")
        return

    if call.data == "admin_verify":
        if call.from_user.id != ADMIN_ID: return
        caption = call.message.caption
        if not caption: return
            
        user_id_match = re.search(r"System ID:\s*<code>(\d+)<\/code>", caption)
        if not user_id_match:
            user_id_match = re.search(r"UserID:\s*(\d+)", caption)
            
        courses_match = re.search(r"Selected Courses:\s*(.+)", caption)
        medium_match = re.search(r"Medium Selected:\s*(HINDI|ENGLISH|N/A)", caption, re.IGNORECASE)
        
        if not (user_id_match and courses_match and medium_match):
            bot.answer_callback_query(call.id, "❌ Error: Could not parse admin caption data!", show_alert=True)
            return
            
        target_uid = int(user_id_match.group(1))
        courses_str = courses_match.group(1)
        medium_str = medium_match.group(1).upper()
        
        bot.answer_callback_query(call.id, "Processing PDF Delivery...")
        
        try:
            records_sheet1 = sheet1.get_all_values()
            course_list = [c.strip() for c in courses_str.split(",")]
            pdf_list = []
            
            for course in course_list:
                s_term = clean_string(course)
                for row in records_sheet1:
                    if len(row) > 3:
                        r_course = clean_string(row[0])
                        r_medium = str(row[1]).strip().upper() if len(row) > 1 and str(row[1]).strip() != "" else "HINDI"
                        
                        if s_term in r_course and medium_str == r_medium:
                            pdf_list.append((row[0], str(row[3]).strip()))
                            break
                            
            if pdf_list:
                bot.send_message(target_uid, "🎉 <b>Payment Verified Successfully!</b>\n\n⏳ <i>Our servers are preparing your high-quality PDFs for direct delivery. Please wait a few seconds...</i>", parse_mode='HTML')
                
                for course_name, drive_url in pdf_list:
                    try:
                        bot.send_chat_action(target_uid, 'upload_document')
                        direct_url = get_direct_drive_url(drive_url)
                        if direct_url:
                            res = requests.get(direct_url, timeout=30)
                            if res.status_code == 200 and res.content.startswith(b'%PDF'):
                                safe_name = course_name.replace(' ', '_')
                                bot.send_document(
                                    target_uid, 
                                    document=(f"{safe_name}.pdf", res.content), 
                                    caption=f"📚 <b>{course_name}</b>\n✅ Premium Solved Assignment (100% Verified)", 
                                    parse_mode='HTML'
                                )
                                continue
                        fallback_msg = f"🔗 <b>{course_name}</b>\n👉 <a href='{drive_url}'>Click Here to Download PDF from Drive</a>"
                        bot.send_message(target_uid, fallback_msg, parse_mode='HTML', disable_web_page_preview=True)
                    except Exception:
                        fallback_msg = f"🔗 <b>{course_name}</b>\n👉 <a href='{drive_url}'>Click Here to Download PDF from Drive</a>"
                        bot.send_message(target_uid, fallback_msg, parse_mode='HTML', disable_web_page_preview=True)
                
                bot.send_message(target_uid, "✅ <b>Delivery Complete!</b>\nAll requested files have been successfully sent. We wish you the best in your studies! 🌟", parse_mode='HTML', reply_markup=get_back_button())
                try: bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=caption + "\n\n<b>[STATUS: APPROVED & DELIVERED ✅]</b>", parse_mode='HTML')
                except Exception: pass
            else:
                bot.answer_callback_query(call.id, "❌ Error: Could not locate exact links in database.", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {e}", show_alert=True)
        return

    if user_id not in USER_STATE:
        bot.answer_callback_query(call.id, "❌ Session Expired. Please restart from Main Menu.", show_alert=True)
        return
        
    order = USER_STATE[user_id]
    
    if call.data.startswith("set_med_"):
        medium = call.data.replace("set_med_", "")
        order['medium'] = medium
        courses = order.get('raw_courses', [])
        
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except: pass
            
        try:
            records_sheet1 = sheet1.get_all_values()
            found_lines = []
            valid_courses = []
            
            for course_input in courses:
                if not course_input.strip(): continue
                s_term = clean_string(course_input)
                matched = False
                for row in records_sheet1:
                    if len(row) > 1:
                        r_course = clean_string(row[0])
                        r_medium = str(row[1]).strip().upper() if len(row) > 1 and str(row[1]).strip() != "" else "HINDI"
                        
                        if s_term in r_course and medium == r_medium:
                            found_lines.append(f"✅ <b>{course_input.upper()}</b> - Available")
                            valid_courses.append(row[0])
                            matched = True
                            break
                if not matched:
                    found_lines.append(f"❌ <b>{course_input.upper()}</b> - Not Available")
                    
            if valid_courses:
                total_price = len(valid_courses) * PRICE_PER_PDF
                order['total'] = total_price
                order['valid_courses'] = valid_courses
                order['discount'] = 0
                
                user_pts = get_user_points(str(user_id))
                
                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(
                    InlineKeyboardButton(f"💳 Checkout (₹{total_price})", callback_data="choice_paid"),
                    InlineKeyboardButton("🆓 Watch Free Tutorial", callback_data="choice_free")
                )
                if user_pts > 0:
                    markup.add(InlineKeyboardButton(f"⭐ Redeem {user_pts} Points (Get ₹{user_pts} Off)", callback_data="redeem_points"))
                markup.add(InlineKeyboardButton("📄 View Live Sample (3 Pages)", callback_data="view_sample"))
                markup.add(
                    InlineKeyboardButton("⬅️ Back", callback_data="back_to_assignment"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
                )
                
                reply_text = (
                    f"📋 <b>Order Availability Report ({medium}):</b>\n\n" +
                    "\n".join(found_lines) + "\n\n" +
                    f"💵 <b>Total Invoice Amount:</b> ₹{total_price} <i>(For {len(valid_courses)} available PDFs)</i>\n"
                    f"⭐ <b>Available Points:</b> {user_pts} Points\n\n"
                    "👇 <i>Please choose your preferred method:</i>"
                )
                bot.send_message(user_id, reply_text, parse_mode='HTML', reply_markup=markup)
            else:
                reply_text = (
                    f"📋 <b>Order Availability Report ({medium}):</b>\n\n" +
                    "\n".join(found_lines) + "\n\n" +
                    f"⚠️ We apologize, none of the requested courses are currently available in <b>{medium}</b> medium."
                )
                bot.send_message(user_id, reply_text, parse_mode='HTML', reply_markup=get_navigation_buttons("back_to_assignment"))
        except Exception as e:
            bot.send_message(user_id, f"❌ System Error: {e}")

    elif call.data == "redeem_points":
        user_pts = get_user_points(str(user_id))
        total = order.get('total', 0)
        if user_pts > 0 and total > 0:
            discount = min(user_pts, total)
            remaining_total = total - discount
            remaining_pts = user_pts - discount
            
            order['total'] = remaining_total
            order['discount'] = discount
            update_user_points(str(user_id), remaining_pts)
            
            try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            except: pass
            
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton(f"💳 Pay ₹{remaining_total}", callback_data="choice_paid"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
            )
            bot.send_message(
                user_id,
                f"✅ <b>Points Redeemed Successfully!</b>\n\n"
                f"🔹 Discount Applied: -₹{discount}\n"
                f"🔹 <b>New Payable Amount: ₹{remaining_total}</b>\n\n"
                f"👇 <i>Click below to proceed to payment:</i>",
                parse_mode='HTML',
                reply_markup=markup
            )
        else:
            bot.answer_callback_query(call.id, "❌ No points available to redeem!", show_alert=True)

    elif call.data == "view_sample":
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except: pass
            
        msg = bot.send_message(user_id, "⏳ <i>Generating a live sample from our secure database... This takes about 10-15 seconds. Please wait.</i>", parse_mode='HTML')
        
        courses = order.get('valid_courses', order.get('raw_courses', []))
        medium = order.get('medium', 'HINDI')
        sample_sent = False
        
        try:
            records_sheet1 = sheet1.get_all_values()
            for course_input in courses:
                s_term = clean_string(course_input)
                for row in records_sheet1:
                    if len(row) > 3:
                        r_course = clean_string(row[0])
                        r_medium = str(row[1]).strip().upper() if len(row) > 1 and str(row[1]).strip() != "" else "HINDI"
                        
                        if s_term in r_course and medium == r_medium:
                            drive_url = str(row[3]).strip()
                            direct_url = get_direct_drive_url(drive_url)
                            if direct_url:
                                res = requests.get(direct_url, timeout=30)
                                if res.status_code == 200 and res.content.startswith(b'%PDF'):
                                    pdf_file = io.BytesIO(res.content)
                                    reader = PdfReader(pdf_file)
                                    writer = PdfWriter()
                                    num_pages = min(3, len(reader.pages))
                                    for i in range(num_pages): writer.add_page(reader.pages[i])
                                    output_pdf = io.BytesIO()
                                    writer.write(output_pdf)
                                    output_pdf.seek(0)
                                    safe_name = row[0].replace(' ', '_')
                                    
                                    markup = InlineKeyboardMarkup(row_width=1)
                                    markup.add(
                                        InlineKeyboardButton("💳 Continue to Full Checkout", callback_data="choice_paid"),
                                        InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
                                    )
                                    
                                    try: bot.delete_message(user_id, msg.message_id)
                                    except: pass
                                    bot.send_document(
                                        user_id,
                                        document=(f"Sample_{safe_name}.pdf", output_pdf.getvalue()),
                                        caption=f"📄 <b>Preview: {row[0]}</b>\n✅ 100% Quality Assurance & High Accuracy.\n\n👇 <i>If you are satisfied with the quality, you may proceed to purchase the complete document:</i>",
                                        parse_mode='HTML',
                                        reply_markup=markup
                                    )
                                    sample_sent = True
                                    break
                if sample_sent: break 
        except Exception: pass
            
        if not sample_sent:
            try: bot.delete_message(user_id, msg.message_id)
            except: pass
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("💳 Proceed to Checkout", callback_data="choice_paid"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
            )
            bot.send_message(user_id, "⚠️ We were unable to automatically generate a sample for this specific format. However, rest assured our material carries a 100% Quality Guarantee.", reply_markup=markup)
            
    elif call.data == "choice_paid":
        total = order.get('total', 20)
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main"))
        
        payment_caption = (
            "💳 <b>Secure Payment Gateway</b>\n\n"
            "Please complete your payment to initiate the automatic delivery of your assignments.\n\n"
            f"🔹 <b>Total Payable Amount:</b> <b>₹{total}</b>\n"
            f"🔹 <b>Official UPI ID:</b> <code>{UPI_ID}</code>\n\n"
            "📌 <b>Next Steps:</b>\n"
            "Once the payment is successful, upload the clear <b>Payment Screenshot</b> directly in this chat.\n"
            "<i>(The system will automatically process your receipt and deliver your PDFs instantly upon admin verification).</i>"
        )
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except: pass
        sent_qr = bot.send_photo(user_id, photo=QR_CODE_URL, caption=payment_caption, parse_mode='HTML', reply_markup=markup)
        USER_STATE[user_id]['qr_msg_id'] = sent_qr.message_id
        
    elif call.data == "choice_free":
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except: pass
            
        courses = order.get('valid_courses', order.get('raw_courses', []))
        medium = order.get('medium', 'HINDI')
        specific_yt_link = ""
        yt_links_text = ""
        
        try:
            records_sheet4 = sheet4.get_all_values()
            for course_input in courses:
                s_term = clean_string(course_input)
                for row in records_sheet4:
                    if len(row) > 3:
                        r_course = clean_string(row[0])
                        r_medium = str(row[1]).strip().upper() if len(row) > 1 and str(row[1]).strip() != "" else "HINDI"
                        
                        if s_term in r_course and medium == r_medium:
                            yt_link = str(row[3]).strip()
                            if yt_link:
                                yt_links_text += f"• <b>{row[0]}</b>: {yt_link}\n"
                                specific_yt_link = yt_link
                            break
        except Exception: pass

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📢 Join Discussion Community", url=FINAL_GROUP_LINK),
            InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
        )
        
        if len(courses) == 1 and specific_yt_link:
            markup.add(InlineKeyboardButton("📺 Watch Video Tutorial", url=specific_yt_link))
            markup.add(InlineKeyboardButton("🔔 Subscribe to Channel", url=YOUTUBE_CHANNEL_LINK))
            reply = (
                "🆓 <b>Free Academic Resource Portal</b>\n\n"
                f"You can prepare your <b>{courses[0]} ({medium})</b> assignment absolutely free by watching our detailed video tutorial.\n\n"
                "👇 <i>Click below to start watching:</i>"
            )
        elif yt_links_text:
            markup.add(InlineKeyboardButton("🔔 Subscribe to Channel", url=YOUTUBE_CHANNEL_LINK))
            reply = (
                "🆓 <b>Free Academic Resource Portal</b>\n\n"
                "We have found the following video tutorials for your requested subjects:\n\n"
                f"{yt_links_text}\n"
                "👇 <i>Please join our community channels for further support:</i>"
            )
        else:
            markup.add(InlineKeyboardButton("📺 Visit YouTube Channel", url=YOUTUBE_CHANNEL_LINK))
            reply = (
                "🆓 <b>Free Academic Resource Portal</b>\n\n"
                "The specific video tutorial for this course is currently not mapped in our database. However, you can search for it directly on our YouTube channel.\n\n"
                "👇 <i>Click below to explore our video library:</i>"
            )

        bot.send_message(user_id, reply, parse_mode='HTML', disable_web_page_preview=True, reply_markup=markup)

# ==========================================
# 📩 MESSAGE HANDLER (CONTINUOUS LISTENING & ADMIN BUTTON FIX)
# ==========================================
@bot.message_handler(func=lambda message: True, content_types=['text', 'audio', 'document', 'photo', 'sticker', 'video', 'video_note', 'voice', 'location', 'contact'])
def continuous_check(message):
    user_id = message.from_user.id
    chat_type = message.chat.type
    
    if chat_type in ['group', 'supergroup']:
        if is_admin(message.chat.id, user_id): return
        if not check_membership(user_id):
            try: bot.delete_message(message.chat.id, message.message_id)
            except: pass
            return 
        if message.content_type == 'document': return 
        try: bot.delete_message(message.chat.id, message.message_id)
        except: pass
            
    elif chat_type == 'private':
        if not check_membership(user_id):
             send_join_message(message.chat.id)
        else:
            if message.content_type == 'photo':
                if ADMIN_ID:
                    if user_id in USER_STATE and 'qr_msg_id' in USER_STATE[user_id]:
                        try:
                            bot.delete_message(chat_id=user_id, message_id=USER_STATE[user_id]['qr_msg_id'])
                            del USER_STATE[user_id]['qr_msg_id']
                        except Exception: pass

                    if user_id in USER_STATE and 'valid_courses' in USER_STATE[user_id]:
                        c_str = ", ".join(USER_STATE[user_id]['valid_courses'])
                        med_str = USER_STATE[user_id].get('medium', 'HINDI')
                    else:
                        c_str = ",".join(USER_STATE[user_id].get('raw_courses', [])) if user_id in USER_STATE else "N/A"
                        med_str = USER_STATE[user_id].get('medium', 'N/A') if user_id in USER_STATE else "N/A"
                        
                    try:
                        forward_caption = (
                            f"🚨 <b>INCOMING PAYMENT RECEIPT!</b>\n\n"
                            f"👤 <b>Client Name:</b> {message.from_user.first_name}\n"
                            f"🆔 <b>System ID:</b> <code>{user_id}</code>\n"
                            f"📚 <b>Selected Courses:</b> {c_str}\n"
                            f"🗣️ <b>Medium Selected:</b> {med_str}\n\n"
                            "Admin: Please verify the transaction and select an action below:"
                        )
                        # 🔥 FIXED: MOBILE BUTTON ALIGNMENT (row_width=1 taaki buttons cut na hon) 🔥
                        markup = InlineKeyboardMarkup(row_width=1)
                        markup.add(
                            InlineKeyboardButton("✅ Verify Payment & Send PDFs", callback_data="admin_verify"),
                            InlineKeyboardButton("❌ Decline Payment", callback_data="admin_reject")
                        )
                        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=forward_caption, parse_mode='HTML', reply_markup=markup)
                        bot.send_message(message.chat.id, "✅ <b>Screenshot Uploaded Successfully!</b>\n\nYour payment is currently under review by our administrators.\n⏳ <b>Estimated Verification Time: Under 30 Minutes.</b>\n\nOnce verified, the premium PDFs will be delivered securely to this chat window.", parse_mode='HTML', reply_to_message_id=message.message_id, reply_markup=get_back_button())
                    except Exception as e:
                        bot.reply_to(message, "❌ An error occurred during transmission. Please contact our support team.")
                elif user_id not in USER_STATE:
                    bot.reply_to(message, "⚠️ System Error: It appears you have not selected any subjects yet. Please select your courses from the Main Menu before uploading a receipt.", reply_markup=get_back_button())
                return

            if message.content_type == 'text' and not message.text.startswith('/'):
                if user_id in WAITING_FOR_ENROLLMENT:
                    WAITING_FOR_ENROLLMENT.remove(user_id)
                    enr_number = message.text.strip()
                    bot.send_message(message.chat.id, f"🔍 <b>Processing Request...</b>\n\n<b>Enrollment Number:</b> <code>{enr_number}</code>\n\n<i>Fetching your latest grade card securely from IGNOU servers. Please wait a few moments...</i>", parse_mode='HTML')
                    fetch_ignou_result(enr_number, message.chat.id)
                
                elif user_id in WAITING_FOR_COURSE:
                    WAITING_FOR_COURSE.remove(user_id)
                    raw_input_text = message.text.strip().upper()
                    courses = [c.strip() for c in raw_input_text.split(',')]
                    USER_STATE[user_id] = {'raw_courses': courses}
                    
                    markup = InlineKeyboardMarkup(row_width=2)
                    markup.add(
                        InlineKeyboardButton("🇮🇳 Hindi Medium", callback_data="set_med_HINDI"),
                        InlineKeyboardButton("🇬🇧 English Medium", callback_data="set_med_ENGLISH")
                    )
                    markup.add(
                        InlineKeyboardButton("⬅️ Back", callback_data="start_assignment"),
                        InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
                    )
                    bot.send_message(message.chat.id, "🗣️ <b>Select Academic Medium:</b>\n\nPlease select the medium/language in which you require the assignments:", parse_mode='HTML', reply_markup=markup)
                else:
                     bot.send_message(message.chat.id, "👇 Please select a service from the official Dashboard below:", parse_mode='HTML', reply_markup=get_main_menu())

# ==========================================
# 🌐 WEBHOOK SETTINGS
# ==========================================
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Student Help Club Corporate Server is actively running!', 200

if __name__ == "__main__":
    RENDER_URL = "https://YOUR_RENDER_URL_HERE" 
    
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=RENDER_URL)
        print(f"Webhook securely established at: {RENDER_URL}")
    except Exception as e:
        print(f"Webhook setting failed: {e}")
        
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
