import discord
import os

from discord.ext import tasks, commands
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

channel_id = 1385026885615882461
channel_id = 1252318623087722538

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    weekly_reminder.start()

@tasks.loop(minutes=1)
async def weekly_reminder():
    now = datetime.now()
    if now.weekday() == 2 and now.hour == 2 and now.minute == 0: # Tuesday 2:00 AM UTC
        channel = bot.get_channel(channel_id)
        if channel:
            with open("maplestory_weekly_reset_additional.png", "rb") as f:
                picture = discord.File(f)
                await channel.send(
                    content="🗓️ Weekly Reset tomorrow! Get your shit done. <@&1385048198950944903>",
                    file=picture
                )
# TEST Command below
@bot.command()
async def test(ctx):
    print("Received !test")
    try:
        with open("maplestory_weekly_reset.png", "rb") as f:
            print("✅ Image file opened")
            picture = discord.File(f)
            await ctx.send("🧪 Test: MapleStory Weekly Reset Reminder!", file=picture)
    except Exception as e:
        print(f"❌ Error: {e}")
        await ctx.send("Failed to load image.")

import traceback
import requests  # Add this at the top if it's not already imported

def send_discord_alert(message: str):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if webhook_url:
        payload = {"content": f"🚨 Bot crashed: {message}"}
        try:
            requests.post(webhook_url, json=payload)
        except Exception as e:
            print("❌ Failed to send crash alert:", e)

try:
    bot.run(os.getenv("DISCORD_TOKEN"))
except Exception as e:
    print("🚨 BOT CRASHED!")
    traceback.print_exc()
    send_discord_alert(str(e))
