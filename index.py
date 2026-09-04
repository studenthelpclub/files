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
ADMIN_ID = int(os.environ.get("1238405133", "0"))  # Apna Admin Telegram ID yahan ya Env mein daalein

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set!")

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)


REQUIRED_CHATS = ['@studenthelpclub', '@studenthelpclubofficial'] 
FINAL_GROUP_LINK = "https://t.me/+YwUmMpjCgHFkZDdl"
YOUTUBE_CHANNEL_LINK = "https://www.youtube.com/@StudentHelpClub"

ASSIGNMENT_WEBSITE = "https://studenthelpclub.in" 
JOBS_WEBSITE = "https://jobs.studenthelpclub.in"
UTILITY_TOOLS = "https://shctools.in/"

# User states ko track karne ke liye temporary memory
WAITING_FOR_ENROLLMENT = set()
WAITING_FOR_COURSE = set()

# --- GOOGLE SHEETS SETUP (Multi-Sheet Support) ---
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    # 1. User Database Sheet
    user_doc = client.open("Student Help Club Data")
    users_sheet = user_doc.worksheet("Users")

    # 2. Master Data Sheet (Dusra Gmail)
    master_doc = client.open("Master Sheet")
    sheet1 = master_doc.worksheet("Sheet1")
    sheet4 = master_doc.worksheet("Sheet4")
except Exception as e:
    print(f"Google Sheets Connection Error: {e}")

def save_user(message):
    """Saves user data to Google Sheet if not already saved."""
    try:
        user_id = str(message.from_user.id)
        existing_users = users_sheet.col_values(1)
        if user_id not in existing_users:
            name = message.from_user.first_name
            username = message.from_user.username or "N/A"
            users_sheet.append_row([user_id, name, username])
    except Exception as e:
        print(f"Error saving user: {e}")

def check_membership(user_id):
    """Checks if the user is present in all REQUIRED_CHATS."""
    for chat_id in REQUIRED_CHATS:
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            print(f"Error checking {chat_id}: {e}")
            return False
    return True

def get_main_menu():
    """Generates the main menu markup with Check Result and Assignment buttons."""
    markup = InlineKeyboardMarkup(row_width=1)
    btn_result = InlineKeyboardButton("🔍 Check IGNOU Result", callback_data="start_check_result")
    btn_assignment = InlineKeyboardButton("📖 Get Assignment PDF", callback_data="start_assignment")
    btn_group = InlineKeyboardButton("📚 IGNOU Solved Assignments", url=FINAL_GROUP_LINK)
    btn_website = InlineKeyboardButton("🌐 Assignment Website", url=ASSIGNMENT_WEBSITE)
    btn_jobs = InlineKeyboardButton("💼 Jobs Updates", url=JOBS_WEBSITE)
    btn_tools = InlineKeyboardButton("🛠️ Utility Tools", url=UTILITY_TOOLS)
    markup.add(btn_result, btn_assignment, btn_group, btn_website, btn_jobs, btn_tools)
    return markup

def send_join_message(chat_id):
    """Sends the force join message with buttons."""
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("📢 Join Main Channel", url="https://t.me/studenthelpclub"))
    markup.add(InlineKeyboardButton("👥 Join Chat Group", url="https://t.me/studenthelpclubofficial"))
    markup.add(InlineKeyboardButton("✅ JOINED", callback_data="verify_join"))
    
    join_msg = (
        "👋 <b>Welcome to Student Help Club Bot!</b>\n\n"
        "📚 IGNOU ke free solved assignments, jobs aur latest updates access karne ke liye, "
        "kripya hamare official channels ko join karein.\n\n"
        "👇 <i>Neeche diye gaye buttons par click karein aur join karne ke baad '✅ JOINED' dabayein.</i>"
    )
    bot.send_message(
        chat_id, 
        join_msg, 
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.message_handler(commands=['start', 'restart'])
def send_welcome(message):
    save_user(message)  # User ko sheet mein save karna
    user_id = message.from_user.id
    command = message.text.split()[0].lower() 
    
    if check_membership(user_id):
        if command == '/restart':
            welcome_text = "🔄 <b>Menu Restarted Successfully!</b>\n\n"
        else:
            welcome_text = "👋 <b>Welcome back to Student Help Club!</b>\n\n"
            
        welcome_text += (
            "Aap already verified member hain. 🎉\n\n"
            "👇 <i>Neeche diye gaye buttons se apni zaroorat ka option select karein:</i>"
        )
        bot.send_message(
            message.chat.id, 
            welcome_text, 
            parse_mode='HTML', 
            reply_markup=get_main_menu()
        )
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
            "👇 <i>Neeche diye gaye buttons se Result check karein, Assignment website, Jobs ya tools access karein:</i>"
        )
        bot.send_message(
            call.message.chat.id, 
            success_msg, 
            parse_mode='HTML',
            reply_markup=get_main_menu()
        )
    else:
        bot.answer_callback_query(
            call.id, 
            "❌ Kripya pehle upar diye gaye dono channels join karein!", 
            show_alert=False
        )

# Jab user "Check Result" button click karega
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
        "📝 <b>Apna Enrollment Number yahan type karke bhejein:</b>",
        parse_mode='HTML'
    )

# Jab user "Get Assignment PDF" button click karega
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
        "📖 <b>Apna IGNOU Course Code type karke bhejein (e.g., BPSC 110 ya BCOC 134):</b>",
        parse_mode='HTML'
    )

# Broadcast Command for Admin
@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Aapko yeh command use karne ki permission nahi hai.")
        return
    
    msg_to_broadcast = message.text.replace("/broadcast", "").strip()
    if not msg_to_broadcast:
        bot.reply_to(message, "Kripya message likhein. Format: `/broadcast Hello everyone!`", parse_mode="Markdown")
        return

    try:
        users = users_sheet.col_values(1)
        success, fail = 0, 0
        bot.reply_to(message, f"📢 Broadcast started to saved users...")
        
        for uid in users:
            if uid.isdigit():
                try:
                    bot.send_message(chat_id=int(uid), text=msg_to_broadcast)
                    success += 1
                    time.sleep(0.1) # Rate limit bachane ke liye
                except Exception:
                    fail += 1
                
        bot.send_message(message.chat.id, f"✅ Broadcast Complete!\nSent: {success}\nFailed: {fail}")
    except Exception as e:
        bot.reply_to(message, f"❌ Broadcast Error: {e}")

def fetch_ignou_result(enr_no, chat_id):
    """Selenium Automation to fetch IGNOU result and take full page screenshot"""
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
                promo_js = """
                var banner = document.createElement('div');
                banner.innerHTML = '<h1 style="background-color:#ffeaa7; color:#d63031; padding:20px; text-align:center; font-family:Arial; border-bottom:4px solid #2d3436; margin:0; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">✅ Result Fetched via Student Help Club Auto-Bot 🚀</h1>';
                document.body.prepend(banner);
                """
                driver.execute_script(promo_js)
                time.sleep(1)
                
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
        caption_text = f"✅ Result for Enrollment: `{enr_no}`\n🚀 Powered by *Student Help Club*"
        with open(file_name, 'rb') as photo:
            bot.send_photo(chat_id, photo=photo, caption=caption_text, parse_mode="Markdown")
        os.remove(file_name)
    else:
        bot.send_message(chat_id, "❌ Server bohot zyada down hai. Kripya thodi der baad dobara try karein!")

def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False

# Assignment Choice Handler (Paid / Free options)
@bot.callback_query_handler(func=lambda call: call.data.startswith("paid_") or call.data.startswith("free_"))
def handle_assignment_choice(call):
    data_parts = call.data.split('_', 1)
    choice = data_parts[0]
    search_term = data_parts[1]
    
    if choice == "paid":
        # Apni QR Code ki direct image link yahan daalein
        qr_image_url = "https://i.postimg.cc/YOUR_QR_CODE/qrcode.jpg" 
        bot.send_photo(
            call.message.chat.id, 
            photo=qr_image_url, 
            caption=(
                f"📲 <b>Payment Details</b>\n\n"
                "Humare paid PDF ka charge ₹25 hai (discounted price sirf <b>₹20</b> hai).\n"
                "Is QR code par <b>₹20</b> pay karein aur payment ka screenshot yahan bhejein.\n"
                "Screenshot verify hote hi PDF aapko bhej diya jayega!"
            ),
            parse_mode='HTML'
        )
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

        reply = (
            f"🆓 <b>Free Assignment Details</b>\n\n"
            f"1️⃣ Pehle hamara group join karein: {FINAL_GROUP_LINK}\n"
            f"2️⃣ Yahan se video dekh kar likhein: {yt_link}"
        )
        bot.send_message(call.message.chat.id, reply, parse_mode='HTML', disable_web_page_preview=False)

@bot.message_handler(func=lambda message: True, content_types=['text', 'audio', 'document', 'photo', 'sticker', 'video', 'video_note', 'voice', 'location', 'contact'])
def continuous_check(message):
    user_id = message.from_user.id
    chat_type = message.chat.type
    
    # 1. Group protection logic
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
            file_name = message.document.file_name.lower() if message.document.file_name else ""
            mime_type = message.document.mime_type if message.document.mime_type else ""
            if mime_type == 'application/pdf' or file_name.endswith('.pdf'):
                return 
                
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
            
    # 2. Private Chat logic
    elif chat_type == 'private':
        if not check_membership(user_id):
             send_join_message(message.chat.id)
        else:
            if message.content_type == 'text' and not message.text.startswith('/'):
                # A. Result Check Enrollment State
                if user_id in WAITING_FOR_ENROLLMENT:
                    WAITING_FOR_ENROLLMENT.remove(user_id)
                    enr_number = message.text.strip()
                    
                    professional_msg = (
                        f"✅ <b>Enrollment Number ({enr_number}) received!</b>\n\n"
                        "⏳ Kuch der mein result isi chat mein aa jayega, "
                        "kripya channel koi leave na karein free assignment aur update ke liye."
                    )
                    bot.send_message(
                        message.chat.id, 
                        professional_msg, 
                        parse_mode='HTML', 
                        reply_markup=get_main_menu()
                    )
                    
                    fetch_ignou_result(enr_number, message.chat.id)
                
                # B. Assignment Course Code State
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
                            btn_paid = InlineKeyboardButton("💰 Paid (₹20)", callback_data=f"paid_{search_term}")
                            btn_free = InlineKeyboardButton("🆓 Free YouTube", callback_data=f"free_{search_term}")
                            markup.add(btn_paid, btn_free)
                            
                            reply_text = (
                                f"✅ <b>{exact_name}</b> ka assignment available hai!\n\n"
                                "Humare paid PDF ka charge ₹25 hai (discounted price sirf <b>₹20</b> padega).\n"
                                "Agar aapko free mein likhna hai, toh YouTube se dekh kar likh sakte hain.\n\n"
                                "Aap kaunsa option lena chahenge?"
                            )
                            bot.send_message(message.chat.id, reply_text, parse_mode='HTML', reply_markup=markup)
                        else:
                            bot.send_message(message.chat.id, f"❌ Sorry, {text} ka assignment abhi available nahi hai.")
                    except Exception as e:
                        bot.send_message(message.chat.id, f"❌ Error fetching assignment: {e}")
                
                else:
                     welcome_text = (
                        "Aap already verified member hain. 🎉\n\n"
                        "👇 <i>Neeche diye gaye buttons se apni zaroorat ka option select karein:</i>"
                    )
                     bot.send_message(
                        message.chat.id, 
                        welcome_text, 
                        parse_mode='HTML', 
                        reply_markup=get_main_menu()
                    )

# Vercel Flask Routes
@app.route('/', methods=['GET', 'POST'])
@app.route('/api/index', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Student Help Club Bot is alive and running 24/7!', 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
