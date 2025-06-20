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
OWNER_ID = 162729945213173761  # Bot owner ID
CHANNEL_ID= 1385026885615882461  

# Use environment variable or static toggle
TEST_MODE_ENABLED = os.getenv("TEST_MODE", "false").lower() == "true"

# ------------------- EVENTS -------------------

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    weekly_reminder.start()

    if TEST_MODE_ENABLED:
        print("🧪 Test mode is ON — awaiting manual command to start test loop.")
        try:
            owner = await bot.fetch_user(OWNER_ID)
            if owner:
                await owner.send("🧪 Bot is online in TEST MODE. Use `!toggle_test` to start the loop.")
        except discord.Forbidden:
            print("⚠️ Couldn't DM the owner on startup.")
    else:
        print("🚀 Production mode active.")

# ------------------- TASKS -------------------

@tasks.loop(minutes=1)
async def weekly_reminder():
    now = datetime.now()
    if now.weekday() == 2 and now.hour == 2 and now.minute == 0:  # Tuesday 2:00 AM UTC
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            with open("maplestory_weekly_reset_additional.png", "rb") as f:
                picture = discord.File(f)
                await channel.send(
                    content="🗓️ Weekly Reset tomorrow! Get your shit done. <@&1385048198950944903>",
                    file=picture
                )

@tasks.loop(minutes=4)
async def test_reminder():
    print("🔁 Test loop running...")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        with open("maplestory_weekly_reset_additional.png", "rb") as f:
            picture = discord.File(f)
            await channel.send("🧪 Test Reminder Loop Active! 🗓️ Weekly Reset tomorrow! Get your shit done. <@&1385701226158620672>", file=picture)

# ------------------- COMMANDS -------------------

@bot.command()
async def test(ctx):
    print("Received !test")
    try:
        with open("maplestory_weekly_reset_additional.png", "rb") as f:
            picture = discord.File(f)
            await ctx.send("🧪 Test: MapleStory Weekly Reset Reminder!", file=picture)
    except Exception as e:
        print(f"❌ Error: {e}")
        await ctx.send("Failed to load image.")

@bot.command()
async def toggle_test(ctx):
    global TEST_MODE_ENABLED

    if ctx.author.id != OWNER_ID:
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            print("⚠️ Missing permissions to delete message.")
        return

    if TEST_MODE_ENABLED:
        if test_reminder.is_running():
            test_reminder.cancel()
            print("🛑 Test reminder loop canceled.")
        TEST_MODE_ENABLED = False
        msg = "🛑 Test mode is now OFF."
    else:
        if not test_reminder.is_running():
            test_reminder.start()
            print("🧪 Test reminder loop started.")
        TEST_MODE_ENABLED = True
        msg = "✅ Test mode is now ON."

    await ctx.send(msg)  # 👈 post status in channel

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        print("⚠️ Missing permissions to delete message.")

@bot.command()
async def status(ctx):
    if ctx.author.id != OWNER_ID:
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            print("⚠️ Missing permissions to delete message.")
        return

    status_message = (
        "🧪 Test mode is currently **ON** ✅"
        if TEST_MODE_ENABLED
        else "🛑 Test mode is currently **OFF**"
    )

    try:
        await ctx.author.send(status_message)
    except discord.Forbidden:
        await ctx.send("📬 Couldn't DM you, but test mode is active.")

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        print("⚠️ Missing permissions to delete message.")

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
