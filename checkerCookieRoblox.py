import telebot
import requests
import os
import re
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = '' ##Enter your bot token
bot = telebot.TeleBot(BOT_TOKEN)

class RobloxCookieChecker:
    def __init__(self):
        self.base_url = "https://users.roblox.com/v1/users/authenticated"
        self.economy_url = "https://economy.roblox.com/v1/user/currency"
        self.premium_url = "https://premiumfeatures.roblox.com/v1/users/%s/premium-membership"
        self.transactions_url = "https://economy.roblox.com/v2/users/%s/transactions?transactionType=Purchase&limit=100"
        self.favorites_url = "https://games.roblox.com/v2/users/%s/favorite/games?accessFilter=2&limit=10"

    def check_cookie(self, cookie):
        headers = {
            'Cookie': f'.ROBLOSECURITY={cookie}',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(self.base_url, headers=headers, timeout=10)
            if response.status_code != 200:
                return None, "❌ Invalid cookie"
            
            user_data = response.json()
            user_id = user_data['id']
            
            robux_balance = 0
            try:
                robux_response = requests.get(self.economy_url, headers=headers, timeout=10)
                if robux_response.status_code == 200:
                    robux_data = robux_response.json()
                    robux_balance = robux_data.get('robux', 0)
            except:
                pass
            
            premium_status = self.check_premium_status(user_id, headers)
            total_spent = self.get_total_spent(user_id, headers)
            favorite_games = self.get_favorite_games(user_id, headers)
            
            account_info = {
                'username': user_data['name'],
                'user_id': user_id,
                'robux_balance': robux_balance,
                'premium': premium_status,
                'total_spent_robux': total_spent,
                'is_verified': user_data.get('isVerified', False),
                'created_date': user_data.get('created', ''),
                'favorite_games': favorite_games
            }
            
            return account_info, None
            
        except Exception as e:
            return None, f"❌ Error"

    def check_premium_status(self, user_id, headers):
        try:
            response = requests.get(self.premium_url % user_id, headers=headers, timeout=5)
            if response.status_code == 200:
                premium_data = response.json()
                return premium_data.get('isPremium', False)
        except:
            pass
        return False

    def get_total_spent(self, user_id, headers):
        try:
            total_spent = 0
            cursor = ""
            max_requests = 3
            request_count = 0
            
            while request_count < max_requests:
                url = self.transactions_url % user_id
                if cursor:
                    url += f"&cursor={cursor}"
                
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code != 200:
                    break
                
                data = response.json()
                transactions = data.get('data', [])
                
                for transaction in transactions:
                    if transaction.get('currency', {}).get('type') == 'Robux':
                        amount = abs(transaction.get('currency', {}).get('amount', 0))
                        total_spent += amount
                
                next_cursor = data.get('nextPageCursor')
                if not next_cursor:
                    break
                cursor = next_cursor
                request_count += 1
                
            return total_spent
            
        except:
            return 0

    def get_favorite_games(self, user_id, headers):
        try:
            response = requests.get(self.favorites_url % user_id, headers=headers, timeout=5)
            if response.status_code == 200:
                games_data = response.json()
                games = []
                for game in games_data.get('data', [])[:5]:
                    game_info = {
                        'name': game.get('name', 'Unknown'),
                        'plays': game.get('placeVisits', 0)
                    }
                    games.append(game_info)
                return games
        except:
            pass
        return []

checker = RobloxCookieChecker()

def extract_cookies(text):
    cookies = []
    
    patterns = [
        r'Cookie:\s*(_\|WARNING:[^|\s]+[^\)\s]*)',
        r'Cookie[=:]\s*([^,\s\n]+)',
        r'(_\|WARNING:-DO-NOT-SHARE-THIS[^|\s]+[^\)\s]*)',
        r'(_\|WARNING:[^|\s]+[^\)\s]*)'
    ]
    
    for pattern in patterns:
        found_cookies = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        for cookie in found_cookies:
            cookie = cookie.strip()
            if cookie.startswith('_|WARNING:') and len(cookie) > 50:
                if cookie.endswith('"') or cookie.endswith("'") or cookie.endswith(')'):
                    cookie = cookie[:-1]
                if cookie not in cookies:
                    cookies.append(cookie)
    
    return cookies

def create_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton('🔍 Check Cookies'))
    return markup

user_states = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = "🤖 Roblox Cookie Checker\n\nPress '🔍 Check Cookies' to start"
    
    user_states[message.chat.id] = {'collecting': False, 'cookies': []}
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_menu())

@bot.message_handler(func=lambda message: message.text == '🔍 Check Cookies')
def start_collecting_cookies(message):
    user_states[message.chat.id] = {'collecting': True, 'cookies': []}
    
    instruction_text = "📥 Send cookies as text or TXT files\nPress '✅ Done' when finished"
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton('✅ Done'))
    markup.add(KeyboardButton('❌ Cancel'))
    
    bot.send_message(message.chat.id, instruction_text, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '✅ Done')
def finish_collecting(message):
    if message.chat.id not in user_states or not user_states[message.chat.id]['collecting']:
        bot.send_message(message.chat.id, "Press '🔍 Check Cookies' first", reply_markup=create_main_menu())
        return
    
    cookies = user_states[message.chat.id]['cookies']
    
    if not cookies:
        bot.send_message(message.chat.id, "❌ No cookies collected", reply_markup=create_main_menu())
        user_states[message.chat.id] = {'collecting': False, 'cookies': []}
        return
    
    temp_file_path = create_cookies_file(message.chat.id, cookies)
    
    with open(temp_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    extracted_cookies = extract_cookies(content)
    
    os.remove(temp_file_path)
    
    if not extracted_cookies:
        bot.send_message(message.chat.id, "❌ Error extracting cookies", reply_markup=create_main_menu())
        user_states[message.chat.id] = {'collecting': False, 'cookies': []}
        return
    
    bot.send_message(message.chat.id, f"🔍 Checking {len(extracted_cookies)} cookies...")
    process_multiple_cookies(message, extracted_cookies)

@bot.message_handler(func=lambda message: message.text == '❌ Cancel')
def cancel_collecting(message):
    user_states[message.chat.id] = {'collecting': False, 'cookies': []}
    bot.send_message(message.chat.id, "❌ Cancelled", reply_markup=create_main_menu())

@bot.message_handler(content_types=['text'])
def handle_text(message):
    if message.text in ['🔍 Check Cookies', '✅ Done', '❌ Cancel']:
        return
    
    if message.chat.id not in user_states or not user_states[message.chat.id]['collecting']:
        bot.send_message(message.chat.id, "❌ Press '🔍 Check Cookies' first", reply_markup=create_main_menu())
        return
    
    cookies = extract_cookies(message.text)
    if not cookies:
        bot.send_message(message.chat.id, "❌ No cookies found")
        return
    
    for cookie in cookies:
        if cookie not in user_states[message.chat.id]['cookies']:
            user_states[message.chat.id]['cookies'].append(cookie)
    
    bot.send_message(message.chat.id, f"✅ Added {len(cookies)} cookies\n📊 Total: {len(user_states[message.chat.id]['cookies'])}")

@bot.message_handler(content_types=['document'])
def handle_file(message):
    if message.chat.id not in user_states or not user_states[message.chat.id]['collecting']:
        bot.send_message(message.chat.id, "❌ Press '🔍 Check Cookies' first", reply_markup=create_main_menu())
        return
    
    if not message.document.file_name.endswith('.txt'):
        bot.send_message(message.chat.id, "❌ Send TXT file")
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        temp_file_path = f"temp_download_{message.chat.id}.txt"
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(downloaded_file)
        
        with open(temp_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        os.remove(temp_file_path)
        
        cookies = extract_cookies(content)
        if not cookies:
            bot.send_message(message.chat.id, "❌ No cookies found in file")
            return
        
        new_cookies = []
        for cookie in cookies:
            if cookie not in user_states[message.chat.id]['cookies']:
                user_states[message.chat.id]['cookies'].append(cookie)
                new_cookies.append(cookie)
        
        if new_cookies:
            bot.send_message(message.chat.id, f"✅ Added {len(new_cookies)} cookies from file\n📊 Total: {len(user_states[message.chat.id]['cookies'])}")
        else:
            bot.send_message(message.chat.id, f"ℹ️ All cookies already added\n📊 Total: {len(user_states[message.chat.id]['cookies'])}")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ File error")

def create_cookies_file(chat_id, cookies):
    temp_file_path = f"cookies_grouped_{chat_id}.txt"
    
    with open(temp_file_path, 'w', encoding='utf-8') as f:
        f.write("=== ROBLOX COOKIES ===\n\n")
        for i, cookie in enumerate(cookies, 1):
            f.write(f"Cookie {i}:\n")
            f.write(f"{cookie}\n")
            f.write("-" * 50 + "\n\n")
    
    return temp_file_path

def process_multiple_cookies(message, cookies):
    total_count = len(cookies)
    valid_count = 0
    total_robux = 0
    total_spent = 0
    premium_count = 0
    verified_count = 0
    total_favorite_games = 0
    all_accounts = []
    
    progress_msg = bot.send_message(message.chat.id, f"🔍 Checking {total_count} cookies\n📊 0/{total_count}")
    
    for i, cookie in enumerate(cookies):
        if i % 2 == 0 or i == len(cookies) - 1:
            try:
                bot.edit_message_text(
                    f"🔍 Checking {total_count} cookies\n📊 {i+1}/{total_count}",
                    message.chat.id,
                    progress_msg.message_id
                )
            except:
                pass
        
        account_info, error = checker.check_cookie(cookie)
        
        if account_info:
            valid_count += 1
            total_robux += account_info['robux_balance']
            total_spent += account_info['total_spent_robux']
            if account_info['premium']:
                premium_count += 1
            if account_info['is_verified']:
                verified_count += 1
            
            total_favorite_games += len(account_info['favorite_games'])
            all_accounts.append(account_info)
    
    user_states[message.chat.id] = {'collecting': False, 'cookies': []}
    
    bot.delete_message(message.chat.id, progress_msg.message_id)
    
    send_final_balance_table(message, all_accounts, total_robux, total_count, valid_count, premium_count, verified_count, total_favorite_games)
    
    bot.send_message(message.chat.id, "✅ Check complete!", reply_markup=create_main_menu())

def send_final_balance_table(message, accounts, total_robux, total_count, valid_count, premium_count, verified_count, total_favorite_games):
    if not accounts:
        bot.send_message(message.chat.id, "❌ No valid accounts")
        return
    
    accounts_sorted = sorted(accounts, key=lambda x: x['robux_balance'], reverse=True)
    
    table_text = "💰 FINAL BALANCE TABLE\n\n"
    table_text += "┌───────┬──────────────────┬─────────────┐\n"
    table_text += "│  №    │     Account      │   Balance   │\n"
    table_text += "├───────┼──────────────────┼─────────────┤\n"
    
    for i, account in enumerate(accounts_sorted, 1):
        username = account['username'][:15] + "..." if len(account['username']) > 15 else account['username']
        balance = f"{account['robux_balance']:,} R$"
        
        num_str = f"│ {i:<5} │"
        user_str = f" {username:<16} │"
        balance_str = f" {balance:<11} │"
        
        table_text += num_str + user_str + balance_str + "\n"
    
    table_text += "├───────┼──────────────────┼─────────────┤\n"
    
    total_balance_str = f"{total_robux:,} R$"
    table_text += f"│ Total │ {len(accounts):<16} │ {total_balance_str:<11} │\n"
    table_text += "└───────┴──────────────────┴─────────────┘\n\n"
    
    table_text += f"📊 Statistics:\n"
    table_text += f"• Total cookies: {total_count}\n"
    table_text += f"• ✅ Valid: {valid_count}\n"
    table_text += f"• ❌ Invalid: {total_count - valid_count}\n"
    table_text += f"• Premium: {premium_count}\n"
    table_text += f"• Verified: {verified_count}\n"
    table_text += f"• Favorite games: {total_favorite_games}\n\n"
    
    table_text += f"💰 Balance stats:\n"
    table_text += f"• Total balance: {total_robux:,} R$\n"
    table_text += f"• Richest: {accounts_sorted[0]['username']} - {accounts_sorted[0]['robux_balance']:,} R$\n"
    if len(accounts_sorted) > 1:
        table_text += f"• Poorest: {accounts_sorted[-1]['username']} - {accounts_sorted[-1]['robux_balance']:,} R$\n"
    
    avg_balance = total_robux // len(accounts) if accounts else 0
    table_text += f"• Average balance: {avg_balance:,} R$\n"
    
    bot.send_message(message.chat.id, f"```\n{table_text}\n```", parse_mode='Markdown')

if __name__ == "__main__":
    print("🤖 Bot started")
    bot.polling(none_stop=True)