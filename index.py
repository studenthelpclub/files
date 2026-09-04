import os
import time
import json
import re
import threading
import requests
from bs4 import BeautifulSoup
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

# Aapke Channels/Groups jahan Auto-Posts jayenge
REQUIRED_CHATS = ['@studenthelpclub', '@studenthelpclubofficial'] 
AUTO_POST_GROUP = '@studenthelpclubofficial'  # YouTube video idhar post honge
AUTO_ALERT_CHANNEL = '@studenthelpclub'       # IGNOU Alerts idhar post honge

FINAL_GROUP_LINK = "https://t.me/+YwUmMpjCgHFkZDdl"
YOUTUBE_CHANNEL_LINK = "https://www.youtube.com/@vishalhelpclub"
ADMIN_USERNAME_LINK = "https://t.me/studenthelpclub1"

ASSIGNMENT_WEBSITE = "https://studenthelpclub.in" 
JOBS_WEBSITE = "https://jobs.studenthelpclub.in"
UTILITY_TOOLS = "https://shctools.in/"

QR_CODE_URL = "https://raw.githubusercontent.com/studenthelpclub/files/main/qrcode.jpg"
UPI_ID = "studenthelpclub@naviaxis"
PRICE_PER_PDF = 20  

WAITING_FOR_ENROLLMENT = set()
WAITING_FOR_COURSE = set()
USER_STATE = {}

# Background Tracking Variables
LAST_SHEET4_ROW = 0
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
# 🚀 BACKGROUND AUTO-TASKS (YOUTUBE & IGNOU)
# ==========================================
def background_auto_tasks():
    global LAST_SHEET4_ROW, LAST_IGNOU_ALERT
    while True:
        try:
            # 1. AUTO YOUTUBE POSTER (Har 15 minute mein check karega)
            records_4 = sheet4.get_all_values()
            current_rows = len(records_4)
            
            # Agar bot pehli baar chalu hua hai, toh purane records yaad kar lega (post nahi karega)
            if LAST_SHEET4_ROW == 0:
                LAST_SHEET4_ROW = current_rows
            
            # Agar naya row add hua hai
            elif current_rows > LAST_SHEET4_ROW:
                for i in range(LAST_SHEET4_ROW, current_rows):
                    row = records_4[i]
                    if len(row) > 3 and row[3].strip() != "":
                        subject_code = str(row[0]).strip().upper()
                        yt_link = str(row[3]).strip()
                        
                        yt_msg = (
                            "🚨 🆕 <b>New Solved Assignment Uploaded!</b> 🆕 🚨\n\n"
                            f"📖 <b>Subject Code:</b> <code>{subject_code}</code>\n\n"
                            "Aapka solved assignment hamare YouTube channel par aa gaya hai. Aap video dekh kar apna assignment aasani se aur bilkul free taiyar kar sakte hain!\n\n"
                            f"📺 <b>Watch Video Here:</b>\n👉 {yt_link}\n\n"
                            "💡 <i>Kripya video ko Like karein, Channel ko Subscribe karein, aur apna next Subject Code Comment box mein zaroor likhein!</i>"
                        )
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton("📺 Watch & Write Now", url=yt_link))
                        bot.send_message(AUTO_POST_GROUP, yt_msg, parse_mode='HTML', reply_markup=markup, disable_web_page_preview=False)
                LAST_SHEET4_ROW = current_rows

            # 2. AUTO IGNOU ALERTS SCRAPER
            try:
                # Basic scraper for IGNOU announcements
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get("http://www.ignou.ac.in/ignou/bulletinboard/announcements/latest/1", headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Yeh tag structure IGNOU ke announcements box ko dhundhta hai
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
                            "📢 <b>IGNOU LATEST OFFICIAL UPDATE</b> 📢\n\n"
                            f"📌 <b>Update:</b> {alert_text}\n\n"
                            "🔗 <b>Official Link:</b>\n"
                            f"👉 <a href='{alert_link}'>Click Here for Details</a>\n\n"
                            "<i>Stay updated with Student Help Club!</i>"
                        )
                        bot.send_message(AUTO_ALERT_CHANNEL, alert_msg, parse_mode='HTML', disable_web_page_preview=True)
                        LAST_IGNOU_ALERT = alert_text
            except Exception as e:
                print("IGNOU Scraper Error:", e)

        except Exception as e:
            print("Background Task Error:", e)
            
        # 30 minute tak wait karega, phir dobara check karega
        time.sleep(1800) 

# Start background thread
bg_thread = threading.Thread(target=background_auto_tasks, daemon=True)
bg_thread.start()
# ==========================================


def save_user(message, mobile="N/A"):
    try:
        user_id = str(message.from_user.id)
        existing_users = users_sheet.col_values(1)
        if user_id not in existing_users:
            name = message.from_user.first_name or "N/A"
            username = message.from_user.username or "N/A"
            users_sheet.append_row([user_id, name, username, mobile])
    except Exception:
        pass

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
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔍 Check Result", callback_data="start_check_result"),
        InlineKeyboardButton("📖 Get PDF", callback_data="start_assignment"),
        InlineKeyboardButton("📚 Assignments Group", url=FINAL_GROUP_LINK),
        InlineKeyboardButton("🌐 Official Website", url=ASSIGNMENT_WEBSITE),
        InlineKeyboardButton("💼 Job Updates", url=JOBS_WEBSITE),
        InlineKeyboardButton("🛠️ Utility Tools", url=UTILITY_TOOLS)
    )
    return markup

def get_back_button():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def handle_back(call):
    user_id = call.from_user.id
    WAITING_FOR_ENROLLMENT.discard(user_id)
    WAITING_FOR_COURSE.discard(user_id)
    if user_id in USER_STATE:
        del USER_STATE[user_id]
        
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    bot.send_message(call.message.chat.id, "👇 <b>Main Menu:</b>\nKripya niche diye gaye menu se apna vikalp chunein:", parse_mode='HTML', reply_markup=get_main_menu())

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
        bot.send_message(call.message.chat.id, "✅ <b>Verification Successful!</b>\n\nDhanyawad! Ab aap verified member hain. 🎉\n👇 <i>Apni service select karein:</i>", parse_mode='HTML', reply_markup=get_main_menu())
    else:
        bot.answer_callback_query(call.id, "❌ Kripya pehle dono channels join karein!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "start_check_result")
def prompt_enrollment(call):
    user_id = call.from_user.id
    if not check_membership(user_id):
        bot.answer_callback_query(call.id, "❌ Kripya channels join karein!", show_alert=True)
        return
    WAITING_FOR_ENROLLMENT.add(user_id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    bot.send_message(call.message.chat.id, "📝 <b>IGNOU Result Portal</b>\n\nKripya apna 10-digit <b>Enrollment Number</b> yahan type karke bhejein:", parse_mode='HTML', reply_markup=get_back_button())

@bot.callback_query_handler(func=lambda call: call.data == "start_assignment")
def prompt_course_code(call):
    user_id = call.from_user.id
    if not check_membership(user_id):
        bot.answer_callback_query(call.id, "❌ Kripya channels join karein!", show_alert=True)
        return
    WAITING_FOR_COURSE.add(user_id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    instruction_msg = (
        "📖 <b>IGNOU Solved Assignment Portal</b>\n\n"
        "Kripya apna <b>Course Code</b> yahan type karke bhejein.\n\n"
        "📌 <i>Multiple subjects ek sath mangwane ke liye format:</i> <code>BPSC 110, BCOC 134, BHIC 132</code>"
    )
    bot.send_message(call.message.chat.id, instruction_msg, parse_mode='HTML', reply_markup=get_back_button())

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Aapko yeh command use karne ki permission nahi hai.")
        return
    msg_to_broadcast = message.text.replace("/broadcast", "").strip()
    if not msg_to_broadcast:
        bot.reply_to(message, "⚠️ Kripya message likhein. Format: `/broadcast [Message]`")
        return
    try:
        users = users_sheet.col_values(1)
        success, fail = 0, 0
        bot.reply_to(message, "📢 Broadcast started...")
        for uid in users:
            if uid.isdigit():
                try:
                    bot.send_message(chat_id=int(uid), text=msg_to_broadcast, parse_mode='HTML')
                    success += 1
                    time.sleep(0.1)
                except Exception:
                    fail += 1
        bot.send_message(message.chat.id, f"✅ <b>Broadcast Report:</b>\nSent: {success}\nFailed: {fail}", parse_mode='HTML')
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
        except Exception:
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

def clean_string(text):
    return re.sub(r'[^A-Z0-9]', '', str(text).upper())

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_med_") or call.data in ["choice_paid", "choice_free", "admin_verify"])
def handle_flow(call):
    user_id = call.message.chat.id
    
    # --- ADMIN VERIFICATION LOGIC ---
    if call.data == "admin_verify":
        if call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Sirf admin ke liye!", show_alert=True)
            return
            
        caption = call.message.caption
        if not caption:
            bot.answer_callback_query(call.id, "❌ Error: Caption missing!", show_alert=True)
            return
            
        user_id_match = re.search(r"UserID:\s*(\d+)", caption)
        courses_match = re.search(r"Courses:\s*(.+)", caption)
        medium_match = re.search(r"Medium:\s*(HINDI|ENGLISH|N/A)", caption, re.IGNORECASE)
        
        if not (user_id_match and courses_match and medium_match):
            bot.answer_callback_query(call.id, "❌ Error: Data not found in text!", show_alert=True)
            return
            
        target_uid = int(user_id_match.group(1))
        courses_str = courses_match.group(1)
        medium_str = medium_match.group(1).upper()
        
        bot.answer_callback_query(call.id, "⏳ PDF Links Generate ho rahe hain...")
        
        try:
            records_sheet1 = sheet1.get_all_values()
            course_list = [c.strip() for c in courses_str.split(",")]
            pdf_links = ""
            
            for course in course_list:
                s_term = clean_string(course)
                for row in records_sheet1:
                    if len(row) > 3:
                        r_course = clean_string(row[0])
                        r_medium = str(row[1]).strip().upper() if len(row) > 1 and str(row[1]).strip() != "" else "HINDI"
                        
                        if s_term in r_course and medium_str == r_medium:
                            pdf_links += f"• <b>{row[0]}</b> ({row[1]}):\n{row[3]}\n\n"
                            break
                            
            if pdf_links:
                user_delivery_msg = (
                    "🎉 <b>Payment Verified Successfully!</b>\n\n"
                    "Aapke requested assignments ke Google Drive links niche diye gaye hain:\n\n"
                    f"{pdf_links}"
                    "📥 Aap in links par click karke apne PDFs download kar sakte hain. Thank you for using Student Help Club!"
                )
                bot.send_message(target_uid, user_delivery_msg, parse_mode='HTML', disable_web_page_preview=True, reply_markup=get_back_button())
                
                try:
                    bot.edit_message_caption(chat_id=call.message.chat.id, message_id=call.message.message_id, caption=caption + "\n\n<b>[STATUS: VERIFIED & SENT ✅]</b>", parse_mode='HTML')
                except Exception:
                    pass
            else:
                bot.answer_callback_query(call.id, "❌ Links Sheet mein nahi mile!", show_alert=True)
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Error: {e}", show_alert=True)
        return

    # --- USER FLOW LOGIC ---
    if user_id not in USER_STATE:
        bot.answer_callback_query(call.id, "❌ Session expired. Kripya Main Menu se restart karein.", show_alert=True)
        return
        
    order = USER_STATE[user_id]
    
    if call.data.startswith("set_med_"):
        medium = call.data.replace("set_med_", "")
        order['medium'] = medium
        courses = order['raw_courses']
        
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
            
        try:
            records_sheet1 = sheet1.get_all_values()
            found_lines = []
            found_valid = False
            
            for course_input in courses:
                s_term = clean_string(course_input)
                matched = False
                for row in records_sheet1:
                    if len(row) > 1:
                        r_course = clean_string(row[0])
                        r_medium = str(row[1]).strip().upper() if len(row) > 1 and str(row[1]).strip() != "" else "HINDI"
                        
                        if s_term in r_course and medium == r_medium:
                            found_lines.append(f"• <b>{row[0]}</b> - ✅ Available")
                            matched = True
                            found_valid = True
                            break
                if not matched:
                    found_lines.append(f"• <b>{course_input}</b> - ❌ Not Available")
                    
            if found_valid:
                total_price = len(courses) * PRICE_PER_PDF
                order['total'] = total_price
                
                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(
                    InlineKeyboardButton(f"💰 Paid PDF (₹{total_price})", callback_data="choice_paid"),
                    InlineKeyboardButton("🆓 Free YouTube", callback_data="choice_free")
                )
                markup.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
                
                reply_text = (
                    f"📋 <b>Aapke Courses ki Availability ({medium}):</b>\n\n" +
                    "\n".join(found_lines) + "\n\n" +
                    f"💵 <b>Total Payable Amount:</b> ₹{total_price}\n\n"
                    "👇 <i>Kripya apna option select karein:</i>"
                )
                bot.send_message(user_id, reply_text, parse_mode='HTML', reply_markup=markup)
            else:
                markup = get_back_button()
                bot.send_message(user_id, f"❌ Maaf kijiyega, aapke courses <b>{medium}</b> medium mein available nahi hain.", parse_mode='HTML', reply_markup=markup)
        except Exception as e:
            bot.send_message(user_id, f"❌ Error: {e}")
            
    elif call.data == "choice_paid":
        total = order.get('total', 20)
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
        
        payment_caption = (
            "💳 <b>Secure Payment Gateway - Student Help Club</b>\n\n"
            f"• <b>Total Payable Amount:</b> <b>₹{total}</b>\n"
            f"• <b>UPI ID:</b> <code>{UPI_ID}</code>\n\n"
            "📌 <b>Next Step:</b>\n"
            "Payment successful hone ke baad apna <b>Screenshot (Photo) yahan chat mein bhejein.</b>\n"
            "(Bot automatically aapka screenshot verification ke liye Admin ko bhej dega)."
        )
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.send_photo(user_id, photo=QR_CODE_URL, caption=payment_caption, parse_mode='HTML', reply_markup=markup)
        
    elif call.data == "choice_free":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
            
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("📢 Join Telegram Assignment Group", url=FINAL_GROUP_LINK),
            InlineKeyboardButton("📺 Watch & Write via YouTube Video", url=YOUTUBE_CHANNEL_LINK),
            InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
        )

        reply = (
            "🆓 <b>Free IGNOU Solved Assignment Access</b>\n\n"
            "Aap bilkul nishulk (Free) mein hamare resources ka upyog karke apna assignment likh sakte hain:\n\n"
            "👇 <i>Neeche diye gaye buttons par click karke group join karein ya video dekhein:</i>"
        )
        bot.send_message(user_id, reply, parse_mode='HTML', reply_markup=markup)

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
            except:
                pass
            return 
        if message.content_type == 'document':
            return 
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
            
    elif chat_type == 'private':
        if not check_membership(user_id):
             send_join_message(message.chat.id)
        else:
            if message.content_type == 'photo':
                if ADMIN_ID:
                    if user_id in USER_STATE and 'raw_courses' in USER_STATE[user_id]:
                        c_str = ",".join(USER_STATE[user_id]['raw_courses'])
                        med_str = USER_STATE[user_id].get('medium', 'HINDI')
                    else:
                        c_str = "N/A"
                        med_str = "N/A"
                        
                    try:
                        forward_caption = (
                            f"🚨 <b>New Payment Screenshot!</b>\n\n"
                            f"👤 <b>User Name:</b> {message.from_user.first_name}\n"
                            f"🆔 <b>UserID:</b> {user_id}\n"
                            f"📚 <b>Courses:</b> {c_str}\n"
                            f"🗣️ <b>Medium:</b> {med_str}\n\n"
                            "Kripya payment verify karke niche diye gaye button par click karein:"
                        )
                        markup = InlineKeyboardMarkup()
                        markup.add(InlineKeyboardButton("✅ Verify & Send PDFs", callback_data="admin_verify"))
                        
                        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=forward_caption, parse_mode='HTML', reply_markup=markup)
                        
                        bot.send_message(message.chat.id, "✅ Aapka payment screenshot admin ke paas bhej diya gaya hai.\n⏳ <b>Max Wait Time: 30 Minutes.</b>\nVerification complete hote hi PDF aapko yahi mil jayega!", parse_mode='HTML', reply_to_message_id=message.message_id, reply_markup=get_back_button())
                    except Exception as e:
                        bot.reply_to(message, "❌ Screenshot bhejne mein error aayi. Kripya @studenthelpclub1 par contact karein.")
                elif user_id not in USER_STATE:
                    bot.reply_to(message, "⚠️ Kripya pehle Menu se course select karein aur phir screenshot bhejein.", reply_markup=get_back_button())
                return

            if message.content_type == 'text' and not message.text.startswith('/'):
                
                if user_id in WAITING_FOR_ENROLLMENT:
                    WAITING_FOR_ENROLLMENT.remove(user_id)
                    enr_number = message.text.strip()
                    bot.send_message(message.chat.id, f"🔍 <b>Enrollment Number ({enr_number}) received!</b>\n\nSystem result fetch kar raha hai, kripya prateeksha karein...", parse_mode='HTML')
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
                    markup.add(InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
                    
                    bot.send_message(
                        message.chat.id,
                        "🗣️ <b>Kripya apna Medium select karein:</b>\n\nAapko kis medium mein assignments chahiye?",
                        parse_mode='HTML',
                        reply_markup=markup
                    )
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
