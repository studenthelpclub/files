import os
import time
import telebot
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Vercel ya Environment se token uthana[cite: 3]
TOKEN = os.environ.get("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set!")

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

REQUIRED_CHATS = ['@studenthelpclub', '@studenthelpclubofficial'] 
FINAL_GROUP_LINK = "https://t.me/+YwUmMpjCgHFkZDdl"

ASSIGNMENT_WEBSITE = "https://studenthelpclub.in" 
JOBS_WEBSITE = "https://jobs.studenthelpclub.in"
UTILITY_TOOLS = "https://shctools.in/"

# User states ko track karne ke liye temporary memory
WAITING_FOR_ENROLLMENT = set()

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
    """Generates the main menu markup with Check Result button."""
    markup = InlineKeyboardMarkup(row_width=1)
    btn_result = InlineKeyboardButton("🔍 Check IGNOU Result", callback_data="start_check_result")
    btn_group = InlineKeyboardButton("📚 IGNOU Solved Assignments", url=FINAL_GROUP_LINK)
    btn_website = InlineKeyboardButton("🌐 Assignment Website", url=ASSIGNMENT_WEBSITE)
    btn_jobs = InlineKeyboardButton("💼 Jobs Updates", url=JOBS_WEBSITE)
    btn_tools = InlineKeyboardButton("🛠️ Utility Tools", url=UTILITY_TOOLS)
    markup.add(btn_result, btn_group, btn_website, btn_jobs, btn_tools)
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

def fetch_ignou_result(enr_no, chat_id):
    """Selenium Automation to fetch IGNOU result and take full page screenshot"""
    options = webdriver.ChromeOptions()
    # Server/Local par background mein chalane ke liye headless mode
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
            
            # 1. Dropdown select
            ddl_result_type = wait.until(EC.presence_of_element_located((By.ID, "ddlresultype")))
            Select(ddl_result_type).select_by_index(1)
            time.sleep(3) # Auto-postback wait for June 2026
            
            # 2. Fill Enrollment Number
            driver.find_element(By.ID, "txtEnrno").send_keys(enr_no)
            
            # 3. Click Search
            driver.find_element(By.ID, "btnlogin").click()
            time.sleep(5)
            
            # Check result loaded
            if "Marks/Grade" in driver.page_source or "view_gradecard.aspx" in driver.current_url:
                # Promo Banner Inject
                promo_js = """
                var banner = document.createElement('div');
                banner.innerHTML = '<h1 style="background-color:#ffeaa7; color:#d63031; padding:20px; text-align:center; font-family:Arial; border-bottom:4px solid #2d3436; margin:0; box-shadow: 0px 4px 6px rgba(0,0,0,0.1);">✅ Result Fetched via Student Help Club Auto-Bot 🚀</h1>';
                document.body.prepend(banner);
                """
                driver.execute_script(promo_js)
                time.sleep(1)
                
                # Full page height screenshot calculation
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

    # Telegram par image bhejna
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
                if user_id in WAITING_FOR_ENROLLMENT:
                    WAITING_FOR_ENROLLMENT.remove(user_id)
                    enr_number = message.text.strip()
                    
                    # Aapka manga gaya professional message
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
                    
                    # Background mein Selenium function call karna result nikalne ke liye
                    fetch_ignou_result(enr_number, message.chat.id)
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

# Vercel Flask Routes[cite: 3]
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
    app.run(host="0.0.0.0", port=5000)