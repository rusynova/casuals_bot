import os
import discord
import traceback
import requests
import asyncio
import json
from datetime import datetime
from discord.ext import commands, tasks
from discord import app_commands
import pytz
from dateutil import parser

# ------------------- CONFIG -------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
OWNER_ID = 162729945213173761
CHANNEL_ID = 1252318623087722538
TEST_MODE_ENABLED = os.getenv("TEST_MODE", "false").lower() == "true"
TIMEZONE_FILE = "user_timezones.json"

# ------------------- UTILITY FUNCTIONS -------------------

def load_timezones():
    if not os.path.exists(TIMEZONE_FILE):
        return {}
    with open(TIMEZONE_FILE, "r") as f:
        return json.load(f)

def save_timezones(data):
    with open(TIMEZONE_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ------------------- EVENTS -------------------

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")
    weekly_reminder.start()

    if TEST_MODE_ENABLED:
        print("🧪 Test mode is ON — awaiting manual command to start test loop.")
        try:
            owner = await bot.fetch_user(OWNER_ID)
            if owner:
                await owner.send("🧪 Bot is online in TEST MODE. Use `/toggle_test` to start the loop.")
        except discord.Forbidden:
            print("⚠️ Couldn't DM the owner on startup.")
    else:
        print("🚀 Production mode active.")

# ------------------- TASKS -------------------

@tasks.loop(minutes=1)
async def weekly_reminder():
    now = datetime.now()
    if now.weekday() == 1 and now.hour == 17 and now.minute == 0: # Tuesday @ 5pm PST
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

# ------------------- SLASH COMMANDS -------------------

@bot.tree.command(name="test", description="Send a test MapleStory weekly reset image")
async def test_command(interaction: discord.Interaction):
    try:
        with open("maplestory_weekly_reset_additional.png", "rb") as f:
            picture = discord.File(f)
            await interaction.response.send_message("🧪 Test Reminder Loop Active! 🗓️ Weekly Reset tomorrow! Get your shit done. <@&1385701226158620672>", file=picture)
    except Exception as e:
        print(f"❌ Error: {e}")
        await interaction.response.send_message("Failed to load image.", ephemeral=True)

@bot.tree.command(name="toggle_test", description="Toggle test mode on or off")
async def toggle_test_command(interaction: discord.Interaction):
    global TEST_MODE_ENABLED

    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ You don’t have permission to do that.", ephemeral=True)
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

    await interaction.response.send_message(msg)

@bot.tree.command(name="status", description="Check if test mode is currently active")
async def status_command(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ You don’t have permission to check this.", ephemeral=True)
        return

    msg = "🧪 Test mode is currently **ON** ✅" if TEST_MODE_ENABLED else "🛑 Test mode is currently **OFF**"
    await interaction.response.send_message(msg, ephemeral=True)

@bot.tree.command(name="clean", description="Clean up a number of recent messages in this channel")
@app_commands.describe(amount="Number of messages to delete")
async def clean_command(interaction: discord.Interaction, amount: int):
    if not interaction.channel.permissions_for(interaction.user).manage_messages:
        await interaction.response.send_message("❌ You need Manage Messages permission.", ephemeral=True)
        return

    await interaction.response.defer()
    deleted = await interaction.channel.purge(limit=amount + 1)
    confirmation = await interaction.followup.send(f"🧹 Deleted {len(deleted) - 1} messages.")
    await asyncio.sleep(10)
    await confirmation.delete()

@bot.tree.command(name="settimezone", description="Set your timezone (e.g. America/New_York)")
@app_commands.describe(tz="Timezone name")
async def set_timezone(interaction: discord.Interaction, tz: str):
    try:
        pytz.timezone(tz)
    except pytz.UnknownTimeZoneError:
        await interaction.response.send_message("❌ Invalid timezone. Use format like America/New_York", ephemeral=True)
        return

    timezones = load_timezones()
    timezones[str(interaction.user.id)] = tz
    save_timezones(timezones)
    await interaction.response.send_message(f"✅ Timezone set to `{tz}`", ephemeral=True)

@bot.tree.command(name="time", description="Convert a time to your timezone")
@app_commands.describe(time="Example: '5pm PST' or 'June 22 7pm' or 'tomorrow 3pm'")
async def time_command(interaction: discord.Interaction, time: str):
    timezones = load_timezones()
    user_id = str(interaction.user.id)

    if user_id not in timezones:
        await interaction.response.send_message("⚠️ You need to set your timezone first using `/settimezone`", ephemeral=True)
        return

    try:
        dt_naive = parser.parse(time, fuzzy=True)
        tz = pytz.timezone(timezones[user_id])
        dt_localized = tz.localize(dt_naive)
        dt_utc = dt_localized.astimezone(pytz.utc)
    except Exception as e:
        await interaction.response.send_message("❌ Failed to parse time. Try 'June 22 7pm' or 'tomorrow 5pm'", ephemeral=True)
        return

    # Format output across major zones
    zones = [
        ("🇺🇸 Pacific", "America/Los_Angeles"),
        ("🇺🇸 Eastern", "America/New_York"),
        ("🇬🇧 UK", "Europe/London"),
        ("🇪🇺 Central Europe", "Europe/Berlin"),
        ("🇦🇺 Sydney", "Australia/Sydney")
    ]

    embed = discord.Embed(title="🕒 Time Conversion", description=f"Original: `{time}`", color=0x00ffcc)
    for label, z in zones:
        z_time = dt_utc.astimezone(pytz.timezone(z))
        embed.add_field(name=label, value=z_time.strftime("%A, %B %d • %I:%M %p"), inline=False)

    await interaction.response.send_message(embed=embed)

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
