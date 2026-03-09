"""
Fake NFT Marketplace Telegram Bot
Author: Colin
Description: A scalable bot for a simulated NFT marketplace.
Users can create, list, and buy visual gifts. Selling requires transferring the gift to admin.
"""

import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Беремо токен із змінної оточення
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN environment variable set")

ADMIN_USERNAME = "@sapamacher"  # Admin username for transfers
DATABASE_FILE = "nft_marketplace.db"

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 1000,
        joined_date TEXT
    )''')
    # NFTs table (visual gifts)
    c.execute('''CREATE TABLE IF NOT EXISTS nfts (
        nft_id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        name TEXT,
        description TEXT,
        image_file_id TEXT,
        price INTEGER,
        is_listed INTEGER DEFAULT 0,
        created_date TEXT,
        FOREIGN KEY(owner_id) REFERENCES users(user_id)
    )''')
    # Marketplace listings (active sales)
    c.execute('''CREATE TABLE IF NOT EXISTS listings (
        listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
        nft_id INTEGER,
        seller_id INTEGER,
        price INTEGER,
        listed_date TEXT,
        FOREIGN KEY(nft_id) REFERENCES nfts(nft_id),
        FOREIGN KEY(seller_id) REFERENCES users(user_id)
    )''')
    conn.commit()
    conn.close()

# Helper functions
def get_user(user_id, username=None):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user and username is not None:
        # Register new user
        now = datetime.now().isoformat()
        c.execute("INSERT INTO users (user_id, username, joined_date) VALUES (?, ?, ?)",
                  (user_id, username, now))
        conn.commit()
        user = (user_id, username, 1000, now)
    conn.close()
    return user

def get_nfts(owner_id=None, listed_only=False):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    if owner_id:
        if listed_only:
            c.execute("SELECT * FROM nfts WHERE owner_id = ? AND is_listed = 1", (owner_id,))
        else:
            c.execute("SELECT * FROM nfts WHERE owner_id = ?", (owner_id,))
    else:
        if listed_only:
            c.execute("SELECT * FROM nfts WHERE is_listed = 1")
        else:
            c.execute("SELECT * FROM nfts")
    nfts = c.fetchall()
    conn.close()
    return nfts

def add_nft(owner_id, name, description, image_file_id, price=0):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute('''INSERT INTO nfts (owner_id, name, description, image_file_id, price, created_date)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (owner_id, name, description, image_file_id, price, now))
    nft_id = c.lastrowid
    conn.commit()
    conn.close()
    return nft_id

def list_nft_for_sale(nft_id, seller_id, price):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    # Update nft record
    c.execute("UPDATE nfts SET price = ?, is_listed = 1 WHERE nft_id = ? AND owner_id = ?",
              (price, nft_id, seller_id))
    # Add to listings
    now = datetime.now().isoformat()
    c.execute("INSERT INTO listings (nft_id, seller_id, price, listed_date) VALUES (?, ?, ?, ?)",
              (nft_id, seller_id, price, now))
    conn.commit()
    conn.close()

def remove_listing(nft_id):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE nfts SET is_listed = 0 WHERE nft_id = ?", (nft_id,))
    c.execute("DELETE FROM listings WHERE nft_id = ?", (nft_id,))
    conn.commit()
    conn.close()

def transfer_nft(nft_id, from_owner, to_owner):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE nfts SET owner_id = ?, is_listed = 0 WHERE nft_id = ? AND owner_id = ?",
              (to_owner, nft_id, from_owner))
    c.execute("DELETE FROM listings WHERE nft_id = ?", (nft_id,))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Bot command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user(user.id, user.username)
    await update.message.reply_text(
        f"Welcome to the NFT Marketplace, {user.first_name}!\n\n"
        "You have 1000 credits to start.\n"
        "Use /market to browse NFTs for sale.\n"
        "Use /my_nfts to see your collection.\n"
        "Use /mint to create a new NFT (visual gift).\n"
        "Use /sell to list one of your NFTs for sale.\n"
        "Use /balance to check your credits."
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = get_user(user.id)
    await update.message.reply_text(f"Your balance: {user_data[2]} credits.")

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    listed_nfts = get_nfts(listed_only=True)
    if not listed_nfts:
        await update.message.reply_text("No NFTs currently for sale.")
        return

    keyboard = []
    for nft in listed_nfts:
        # nft: (nft_id, owner_id, name, description, image_file_id, price, is_listed, created_date)
        button = InlineKeyboardButton(
            f"{nft[2]} - {nft[5]} credits",
            callback_data=f"view_{nft[0]}"
        )
        keyboard.append([button])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("NFT Marketplace:", reply_markup=reply_markup)

async def my_nfts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    nfts = get_nfts(owner_id=user.id)
    if not nfts:
        await update.message.reply_text("You don't own any NFTs yet. Use /mint to create one.")
        return

    for nft in nfts:
        caption = f"*{nft[2]}*\n{nft[3]}\nPrice: {nft[5]} credits\nListed: {'Yes' if nft[6] else 'No'}"
        await update.message.reply_photo(
            photo=nft[4],
            caption=caption,
            parse_mode='Markdown'
        )

async def mint_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Initiate minting process
    await update.message.reply_text(
        "Let's create a new NFT! Please send me an image for your NFT."
    )
    context.user_data['minting'] = True
    context.user_data['mint_step'] = 'image'

async def handle_mint_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('minting'):
        return

    photo = update.message.photo[-1]  # largest size
    context.user_data['nft_image'] = photo.file_id
    context.user_data['mint_step'] = 'name'
    await update.message.reply_text("Great! Now send me a name for your NFT.")

async def handle_mint_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('mint_step') != 'name':
        return

    context.user_data['nft_name'] = update.message.text
    context.user_data['mint_step'] = 'description'
    await update.message.reply_text("Now send me a description for your NFT.")

async def handle_mint_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('mint_step') != 'description':
        return

    description = update.message.text
    user = update.effective_user
    nft_id = add_nft(
        owner_id=user.id,
        name=context.user_data['nft_name'],
        description=description,
        image_file_id=context.user_data['nft_image']
    )

    # Clear minting state
    context.user_data.pop('minting', None)
    context.user_data.pop('mint_step', None)
    context.user_data.pop('nft_image', None)
    context.user_data.pop('nft_name', None)

    await update.message.reply_text(
        f"NFT created successfully! ID: {nft_id}\n"
        f"Use /sell to list it on the marketplace."
    )

async def sell_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    nfts = get_nfts(owner_id=user.id, listed_only=False)
    unsold = [n for n in nfts if not n[6]]  # not listed
    if not unsold:
        await update.message.reply_text("You have no NFTs available for sale.")
        return

    # Let user choose which NFT to sell
    keyboard = []
    for nft in unsold:
        button = InlineKeyboardButton(
            f"{nft[2]} (ID: {nft[0]})",
            callback_data=f"sell_choose_{nft[0]}"
        )
        keyboard.append([button])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Select the NFT you want to sell:",
        reply_markup=reply_markup
    )

async def sell_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    nft_id = int(query.data.split('_')[2])
    context.user_data['selling_nft'] = nft_id
    await query.edit_message_text(
        "Please enter the price (in credits) you want to sell this NFT for.\n"
        "Note: To complete the sale, you must transfer the original visual gift (image) to the admin "
        f"(@{ADMIN_USERNAME}) privately. After transfer, the bot will verify and list it."
    )
    context.user_data['sell_step'] = 'price'

async def handle_sell_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('sell_step') == 'price':
        return

    try:
        price = int(update.message.text)
        if price <= 0:
            raise ValueError
    except:
        await update.message.reply_text("Invalid price. Please enter a positive integer.")
        return

    nft_id = context.user_data['selling_nft']
    user = update.effective_user

    # Fetch NFT details
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM nfts WHERE nft_id = ?", (nft_id,))
    nft = c.fetchone()
    conn.close()

    if not nft or nft[1] != user.id:
        await update.message.reply_text("NFT not found or you don't own it.")
        context.user_data.pop('sell_step', None)
        context.user_data.pop('selling_nft', None)
        return

    # Store price and wait for transfer confirmation
    context.user_data['sell_price'] = price
    context.user_data['sell_step'] = 'wait_transfer'

    # Instruct user to transfer the original image to admin
    await update.message.reply_text(
        f"Please forward the original image of this NFT to {ADMIN_USERNAME}.\n"
        "After you forward it, send /confirm_transfer to finalize the listing."
    )

async def confirm_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('sell_step') == 'wait_transfer':
        await update.message.reply_text("No pending sale.")
        return

    nft_id = context.user_data['selling_nft']
    price = context.user_data['sell_price']
    user = update.effective_user

    list_nft_for_sale(nft_id, user.id, price)

    context.user_data.pop('sell_step', None)
    context.user_data.pop('selling_nft', None)
    context.user_data.pop('sell_price', None)

    await update.message.reply_text(
        f"Your NFT is now listed for {price} credits!\n"
        "When someone buys it, the credits will be added to your balance, and the NFT will be transferred."
    )

async def view_nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    nft_id = int(query.data.split('_')[1])
    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM nfts WHERE nft_id = ?", (nft_id,))
    nft = c.fetchone()
    conn.close()

    if not nft or not nft[6]:  # not listed
        await query.edit_message_text("This NFT is no longer available.")
        return

    caption = f"*{nft[2]}*\n{nft[3]}\nPrice: {nft[5]} credits\nSeller ID: {nft[1]}"
    keyboard = [
        [InlineKeyboardButton("Buy", callback_data=f"buy_{nft[0]}")],
        [InlineKeyboardButton("Back to Market", callback_data="back_market")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send photo
    await query.message.reply_photo(
        photo=nft[4],
        caption=caption,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    await query.delete_message()

async def buy_nft(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    nft_id = int(query.data.split('_')[1])
    buyer = update.effective_user

    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM nfts WHERE nft_id = ?", (nft_id,))
    nft = c.fetchone()
    if not nft or not nft[6]:
        await query.edit_message_text("This NFT is no longer for sale.")
        conn.close()
        return

    price = nft[5]
    seller_id = nft[1]

    # Check buyer balance
    c.execute("SELECT balance FROM users WHERE user_id = ?", (buyer.id,))
    buyer_balance = c.fetchone()[0]

    if buyer_balance < price:
        await query.edit_message_text("Insufficient credits.")
        conn.close()
        return

    # Perform transaction
    update_balance(buyer.id, -price)
    update_balance(seller_id, price)

    # Transfer NFT
    transfer_nft(nft_id, seller_id, buyer.id)

    conn.close()

    await query.edit_message_text(
        f"Purchase successful! You now own '{nft[2]}'.\n"
        "Check /my_nfts to view it."
    )

async def back_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Re-show market list
    listed_nfts = get_nfts(listed_only=True)
    if not listed_nfts:
        await query.edit_message_text("No NFTs currently for sale.")
        return

    keyboard = []
    for nft in listed_nfts:
        button = InlineKeyboardButton(
            f"{nft[2]} - {nft[5]} credits",
            callback_data=f"view_{nft[0]}"
        )
        keyboard.append([button])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("NFT Marketplace:", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Route messages based on state
    if context.user_data.get('minting'):
        if context.user_data.get('mint_step') == 'image':
            await handle_mint_image(update, context)
        elif context.user_data.get('mint_step') == 'name':
            await handle_mint_name(update, context)
        elif context.user_data.get('mint_step') == 'description':
            await handle_mint_description(update, context)
    elif context.user_data.get('sell_step') == 'price':
        await handle_sell_price(update, context)
    else:
        # Default fallback
        await update.message.reply_text("Use /start to see available commands.")

# Admin command (optional) to verify transfer
async def admin_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME.replace('@', ''):
        await update.message.reply_text("Unauthorized.")
        return
    # Expect: /confirm <user_id> <nft_id>
    try:
        _, target_user, nft_id = update.message.text.split()
        target_user = int(target_user)
        nft_id = int(nft_id)
    except:
        await update.message.reply_text("Usage: /confirm <user_id> <nft_id>")
        return

    await update.message.reply_text(f"Transfer confirmed for NFT {nft_id} from user {target_user}.")

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("market", market))
    application.add_handler(CommandHandler("my_nfts", my_nfts))
    application.add_handler(CommandHandler("mint", mint_start))
    application.add_handler(CommandHandler("sell", sell_start))
    application.add_handler(CommandHandler("confirm_transfer", confirm_transfer))
    application.add_handler(CommandHandler("confirm", admin_confirm))  # admin command

    # Callback query handlers
    application.add_handler(CallbackQueryHandler(view_nft, pattern="^view_"))
    application.add_handler(CallbackQueryHandler(buy_nft, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(back_market, pattern="^back_market$"))
    application.add_handler(CallbackQueryHandler(sell_choose, pattern="^sell_choose_"))

    # Message handler for text and photos
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start bot
    application.run_polling()

if __name__ == "__main__":
    main()
