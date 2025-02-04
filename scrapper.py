import re
import os
import asyncio
from urllib.parse import urlparse
from pyrogram.enums import ParseMode
from pyrogram import Client, filters
from config import API_ID, API_HASH, SESSION_STRING, BOT_TOKEN, ADMIN_IDS, DEFAULT_LIMIT, ADMIN_LIMIT

# Initialize the bot and user clients
bot = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=1000,
    parse_mode=ParseMode.HTML
)

user = Client(
    "user_session",
    session_string=SESSION_STRING,
    workers=1000
)

scrape_queue = asyncio.Queue()

def remove_duplicates(messages):
    unique_messages = list(set(messages))
    duplicates_removed = len(messages) - len(unique_messages)
    return unique_messages, duplicates_removed

async def scrape_messages(client, channel_username, limit, start_number=None, bank_name=None):
    messages = []
    count = 0
    pattern = r'\d{16}\D*\d{2}\D*\d{2,4}\D*\d{3,4}'
    
    async for message in user.search_messages(channel_username):
        if count >= limit:
            break
        text = message.text if message.text else message.caption
        if text:
            matched_messages = re.findall(pattern, text)
            if matched_messages:
                formatted_messages = []
                for matched_message in matched_messages:
                    extracted_values = re.findall(r'\d+', matched_message)
                    if len(extracted_values) == 4:
                        card_number, mo, year, cvv = extracted_values
                        year = year[-2:]

                        # Check if bank name is mentioned
                        if bank_name and bank_name.lower() not in text.lower():
                            continue  # Skip if the bank name is not found

                        formatted_messages.append(f"{card_number}|{mo}|{year}|{cvv}")
                messages.extend(formatted_messages)
                count += len(formatted_messages)
    
    if start_number:
        messages = [msg for msg in messages if msg.startswith(start_number)]
    
    messages = messages[:limit]
    return messages

@bot.on_message(filters.command(["scr"]))
async def scr_cmd(client, message):
    args = message.text.split()[1:]
    if len(args) < 2 or len(args) > 4:
        await message.reply_text("<b>⚠️ Provide channel username, amount, and optional BIN or bank name.</b>")
        return
    
    channel_identifier = args[0]
    limit = int(args[1])
    start_number = args[2] if len(args) >= 3 and args[2].isdigit() else None
    bank_name = args[3] if len(args) == 4 else (args[2] if len(args) == 3 and not args[2].isdigit() else None)
    
    max_lim = ADMIN_LIMIT if message.from_user.id in ADMIN_IDS else DEFAULT_LIMIT
    if limit > max_lim:
        await message.reply_text(f"<b>Sorry! Maximum limit is {max_lim} ❌</b>")
        return

    parsed_url = urlparse(channel_identifier)
    channel_username = parsed_url.path.lstrip('/') if not parsed_url.scheme else channel_identifier

    try:
        chat = await user.get_chat(channel_username)
        channel_name = chat.title
    except Exception:
        await message.reply_text("<b>Invalid channel username ❌</b>")
        return

    # Image URL for the "Scraping in progress..." message
    processing_image_url = "https://cdn.glitch.global/e8b923da-576d-430b-bc8b-36ee860034c0/IMG_20250203_182522_096.jpg?v=1738587359017"  # replace this with your hosted image URL
    temporary_msg = await message.reply_photo(
        processing_image_url, 
        caption="<b>Scraping in progress... Please wait.</b>"
    )

    scrapped_results = await scrape_messages(user, chat.id, limit, start_number, bank_name)
    unique_messages, duplicates_removed = remove_duplicates(scrapped_results)

    if unique_messages:
        file_name = f"x{len(unique_messages)}_{channel_name.replace(' ', '_')}.txt"
        with open(file_name, 'w') as f:
            f.write("\n".join(unique_messages))
        with open(file_name, 'rb') as f:
            caption = (
                f"<b>✅ Scraping Completed</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📌 <b>Source:</b> <code>{channel_name}</code>\n"
                f"📌 <b>Amount:</b> <code>{len(unique_messages)}</code>\n"
                f"📌 <b>Duplicates Removed:</b> <code>{duplicates_removed}</code>\n"
                f"📌 <b>Filter:</b> <code>{'None' if not bank_name else bank_name}</code>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🔗 <b>Scraper By:</b> <a href='https://t.me/Rio_scrapper'>𝙍𝙄𝙊 𝙎𝘾𝙍𝘼𝙋𝙋𝙀𝙍</a>\n"
            )
            await temporary_msg.delete()  # Delete the "Scraping in progress" message
            await client.send_document(message.chat.id, f, caption=caption)
        os.remove(file_name)
    else:
        await temporary_msg.delete()
        await client.send_message(message.chat.id, "<b>No matching cards found ❌</b>")

@bot.on_message(filters.command("start"))
async def start_command(client, message):
    welcome_text = (
        "<b>👋 Welcome to 𝙍𝙄𝙊 𝙎𝘾𝙍𝘼𝙋𝙋𝙀𝙍 𝘽𝙊𝙏</b>\n\n"
        "🔹 Use /scr to start scraping.\n"
        "🔹 Provide channel username, amount, and optional filters.\n\n"
        "<b>Examples:</b>\n"
        "✔ <code>/scr @channel_username 1000</code> (Basic Scrape)\n"
        "✔ <code>/scr @channel_username 1000 434769</code> (Filter by BIN)\n"
        "✔ <code>/scr @channel_username 1000 Chase</code> (Filter by Bank Name)\n"
        "✔ <code>/scr @channel_username 1000 434769 Chase</code> (Filter by BIN & Bank)\n\n"
        "⚠️ <b>Note:</b> Free users can scrape up to 10,000 only.\n"
        "🔗 <b>Developer:</b> <a href='https://t.me/Rio_Xy1'>𝙍𝙄𝙊</a>"
    )
    
    # Send a video hosted on Telegram
    video_url = "https://cdn.glitch.global/e8b923da-576d-430b-bc8b-36ee860034c0/welcome_video.mp4?v=1738587343509"  # replace this with your actual video URL
    await message.reply_video(video_url, caption=welcome_text)
if __name__ == "__main__":
    user.start()
    bot.run()