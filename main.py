import os
import discord
import traceback
import requests
from datetime import datetime
from discord.ext import commands, tasks

# ------------------- CONFIG -------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
OWNER_ID = 123456789012345678  # Replace with your user ID
channel_id = 1252318623087722538  # Replace with your channel ID

# Use environment variable or static toggle
TEST_MODE_ENABLED = os.getenv("TEST_MODE", "false").lower() == "true"

# ------------------- EVENTS -------------------

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    weekly_reminder.start()
    if TEST_MODE_ENABLED:
        print("🧪 Test mode is ON — starting test_reminder loop.")
        test_reminder.start()

# ------------------- TASKS -------------------

@tasks.loop(minutes=1)
async def weekly_reminder():
    now = datetime.now()
    if now.weekday() == 2 and now.hour == 2 and now.minute == 0:  # Tuesday 2:00 AM UTC
        channel = bot.get_channel(channel_id)
        if channel:
            with open("maplestory_weekly_reset_additional.png", "rb") as f:
                picture = discord.File(f)
                await channel.send(
                    content="🗓️ Weekly Reset tomorrow! Get your shit done. <@&1385048198950944903>",
                    file=picture
                )

@tasks.loop(minutes=1)
async def test_reminder():
    print("🔁 Test loop running...")
    channel = bot.get_channel(channel_id)
    if channel:
        with open("maplestory_weekly_reset_additional.png", "rb") as f:
            picture = discord.File(f)
            await channel.send("🧪 Test Reminder Loop Active!", file=picture)

# ------------------- COMMANDS -------------------

@bot.command()
async def test(ctx):
    print("Received !test")
    try:
        with open("maplestory_weekly_reset.png", "rb") as f:
            picture = discord.File(f)
            await ctx.send("🧪 Test: MapleStory Weekly Reset Reminder!", file=picture)
    except Exception as e:
        print(f"❌ Error: {e}")
        await ctx.send("Failed to load image.")

@bot.command()
async def toggle_test(ctx):
    global TEST_MODE_ENABLED

    if ctx.author.id != OWNER_ID:
        await ctx.message.delete()
        return

    TEST_MODE_ENABLED = not TEST_MODE_ENABLED

    if TEST_MODE_ENABLED:
        test_reminder.start()
        status = "✅ Test mode is now ON."
    else:
        test_reminder.cancel()
        status = "🛑 Test mode is now OFF."

    try:
        await ctx.author.send(status)
    except discord.Forbidden:
        await ctx.send("✅ Toggled, but I couldn't DM you!")

    await ctx.message.delete()

# ------------------- ERROR HANDLING -------------------

def send_discord_alert(message: str):
    if DISCORD_WEBHOOK:
        payload = {"content": f"🚨 Bot crashed: {message}"}
        try:
            requests.post(DISCORD_WEBHOOK, json=payload)
        except Exception as e:
            print("❌ Failed to send crash alert:", e)

try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    print("🚨 BOT CRASHED!")
    traceback.print_exc()
    send_discord_alert(str(e))
