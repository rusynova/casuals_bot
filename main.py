import os
from dotenv import load_dotenv
load_dotenv()

import discord
import traceback
import requests
import asyncio
import json
import pytz
import aiohttp
from datetime import datetime, timezone
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Select, Button
from dateutil import parser

# ------------------- CONFIG -------------------

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
OWNER_ID = 162729945213173761
CHANNEL_ID = 1385889605194088498
TEST_MODE_ENABLED = os.getenv("TEST_MODE", "false").lower() == "true"
TIMEZONE_FILE = "user_timezones.json"
GUILD_ID = 401584720288153600
current_time = datetime.now(timezone.utc).strftime("%-I:%M%p").lower()
SEEN_MOVIE_IDS = set()
JELLYFIN_URL = os.getenv("JELLYFIN_URL")
JELLYFIN_API_KEY = os.getenv("JELLYFIN_API_KEY")
MOVIES_LIBRARY_ID = os.getenv("MOVIES_LIBRARY_ID")
MOVIE_ALERT_THREAD_ID = int(os.getenv("MOVIE_ALERT_THREAD_ID"))


# ------------------- UTILITY FUNCTIONS -------------------

def load_timezones():
    if not os.path.exists(TIMEZONE_FILE):
        return {}
    with open(TIMEZONE_FILE, "r") as f:
        return json.load(f)

def save_timezones(data):
    with open(TIMEZONE_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ------------------- WEEKLY BOSS PRIO -------------------

# Weekly rotation schedule
rotation = [
    {"joshua": "Bowmaster", "mark": "Bucc"},
    {"joshua": "Shade", "mark": "Bowmaster"},
]

start_date = datetime(2025, 9, 2)  # The first week of the rotation

def get_current_week_rotation():
    delta_weeks = (datetime.now().date() - start_date.date()).days // 7
    index = delta_weeks % len(rotation)
    return rotation[index]

def generate_prio_image(joshua_class, mark_class):
    # Create a blank image
    img = Image.new('RGB', (600, 200), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    # Fonts
    font_title = ImageFont.truetype(font_path, 30)
    font_text = ImageFont.truetype(font_path, 24)

    # Add text
    draw.text((20, 20), f"🗡️ Joshua's Prio: {joshua_class}", font=font_text, fill=(255, 255, 255))
    draw.text((20, 80), f"🛡️ Mark's Prio: {mark_class}", font=font_text, fill=(255, 255, 255))

    # Save to file
    filename = "maplestory_weekly_prio.png"
    img.save(filename)
    return filename
#------------------- PAGINATED TIMEZONES ------------------

class PaginatedTimezoneDropdown(Select):
    def __init__(self, page=0):
        self.timezones = sorted(pytz.common_timezones)
        self.page = page
        per_page = 25
        start = page * per_page
        end = start + per_page

        options = [
            discord.SelectOption(label=tz, value=tz)
            for tz in self.timezones[start:end]
        ]

        super().__init__(
            placeholder=f"Select timezone (Page {page + 1})",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"timezone_select_{page}"
        )

    async def callback(self, interaction: discord.Interaction):
        selected_tz = self.values[0]
        timezones = load_timezones()
        timezones[str(interaction.user.id)] = selected_tz
        save_timezones(timezones)
        await interaction.response.send_message(f"✅ Timezone set to `{selected_tz}`", ephemeral=True)

class PaginatedTimezoneView(View):
    def __init__(self, page=0):
        super().__init__()
        self.page = page
        self.max_pages = (len(pytz.common_timezones) - 1) // 25
        self.add_item(PaginatedTimezoneDropdown(page))

        if self.page > 0:
            self.add_item(Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary, custom_id="prev_page"))
        if self.page < self.max_pages:
            self.add_item(Button(label="➡️ Next", style=discord.ButtonStyle.secondary, custom_id="next_page"))

# ------------------- TIMEZONE DROPDOWNS -------------------

POPULAR_TIMEZONES = [
    ("\U0001F1FA\U0001F1F8 Pacific (Oregon)", "America/Los_Angeles"),
    ("\U0001F1FA\U0001F1F8 Mountain (Colorado)", "America/Denver"),
    ("\U0001F1FA\U0001F1F8 Central (Minnesota)", "America/Chicago"),
    ("\U0001F1FA\U0001F1F8 Eastern (Florida)", "America/New_York"),
    ("\U0001F1EC\U0001F1E7 UK", "Europe/London"),
    ("\U0001F1EA\U0001F1FA Central Europe", "Europe/Berlin"),
    ("\U0001F1E6\U0001F1FA Sydney", "Australia/Sydney")
]

class PopularTimezoneDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=label, value=tz)
            for label, tz in POPULAR_TIMEZONES
        ]
        super().__init__(
            placeholder="Choose a popular timezone...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_tz = self.values[0]
        timezones = load_timezones()
        timezones[str(interaction.user.id)] = selected_tz
        save_timezones(timezones)
        await interaction.response.send_message(f"✅ Timezone set to `{selected_tz}`", ephemeral=True)

class TimezoneView(View):
    def __init__(self):
        super().__init__()
        self.add_item(PopularTimezoneDropdown())
        self.add_item(Button(label="📚 Additional Timezones", custom_id="advanced_timezone", style=discord.ButtonStyle.secondary))

# ------------------- INTERACTION HANDLING -------------------

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        if custom_id == "advanced_timezone":
            await interaction.response.send_message("🌍 Select from all timezones:", view=PaginatedTimezoneView(), ephemeral=True)
        elif custom_id in ("next_page", "prev_page"):
            try:
                current_page = int(interaction.message.components[0].children[0].custom_id.split("_")[-1])
                new_page = current_page + 1 if custom_id == "next_page" else current_page - 1
                await interaction.response.edit_message(view=PaginatedTimezoneView(page=new_page))
            except Exception as e:
                await interaction.response.send_message("❌ Failed to paginate timezones.", ephemeral=True)
        
# ------------------- EVENTS -------------------

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    guild = discord.Object(id=GUILD_ID)

    try:
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced commands to guild {guild.id}")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    # Start only the appropriate tasks
    if not weekly_reminder.is_running():
        weekly_reminder.start()
        
    if TEST_MODE_ENABLED:
        if not test_reminder.is_running():
            test_reminder.start()
    else:
        if test_reminder.is_running():
            test_reminder.cancel()  # ensure it's stopped if previously running

    if not update_clock_channel.is_running():
        update_clock_channel.start()

    if not heartbeat.is_running():
        heartbeat.start()
    
    if not check_for_new_movies.is_running():
    check_for_new_movies.start()

    if not weekly_prio_notification.running():
        weekly_prio_notification.start()
    


# ------------------- TASKS -------------------
@tasks.loop(minutes=10)
async def check_for_new_movies():
    await bot.wait_until_ready()
    url = f"{JELLYFIN_URL}/Users/Public/Items?IncludeItemTypes=Movie&ParentId={MOVIES_LIBRARY_ID}&SortBy=DateCreated&SortOrder=Descending&Limit=5"

    headers = {
        "X-Emby-Token": JELLYFIN_API_KEY
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                print(f"Failed to fetch movies: {resp.status}")
                return
            data = await resp.json()
            items = data.get("Items", [])
            new_items = [item for item in items if item["Id"] not in SEEN_MOVIE_IDS]

            if not new_items:
                return

            thread = await bot.fetch_channel(MOVIE_ALERT_THREAD_ID)
            for item in reversed(new_items):  # oldest to newest
                title = item.get("Name", "Unknown Title")
                year = item.get("ProductionYear", "")
                poster = f"{JELLYFIN_URL}/Items/{item['Id']}/Images/Primary"
                message = f"🎬 **New Movie Added**: {title} ({year})\n{poster}"
                await thread.send(message)
                SEEN_MOVIE_IDS.add(item["Id"])
import discord
from discord.ext import tasks, commands
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

intents = discord.Intents.default()
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)

CHANNEL_ID = 123456789012345678  # replace with your channel
font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # adjust path to a ttf font

# Weekly reminder for Loot Prio
@tasks.loop(minutes=1)
async def weekly_prio_notification():
    now = datetime.now()
    if now.weekday() == 1 and now.hour == 17 and now.minute == 0:  # Tuesday 5PM PST
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            rotation_this_week = get_current_week_rotation()
            image_file = generate_prio_image(rotation_this_week["joshua"], rotation_this_week["mark"])
            await channel.send(
                content="📅 Weekly MapleStory Boss Drop Priority! <@1414707967630246060>",
                file=discord.File(image_file)
            )


# Weekly reminder task
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

# Test Loop task
@tasks.loop(minutes=4)
async def test_reminder():
    print("🔁 Test loop running...")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        with open("maplestory_weekly_reset_additional.png", "rb") as f:
            picture = discord.File(f)
            await channel.send("🧪 Test Reminder Loop Active! 🗓️ Weekly Reset tomorrow! Get your shit done. <@&1385701226158620672>", file=picture)
            
# UTC Clock task
@tasks.loop(minutes=6)  # Use a safe interval to stay under rate limits
async def update_clock_channel():
    current_time = datetime.now(timezone.utc).strftime("%I:%M%p").lstrip("0").lower()
    new_name = f"🕒 UTC: {current_time}"

    for guild in bot.guilds:
        for channel in guild.voice_channels:
            if channel.name.startswith("🕒 UTC:"):
                print(f"🕒 Desired: {new_name} | Current: {channel.name}")
                if channel.name != new_name:
                    try:
                        await channel.edit(name=new_name)
                        print(f"✅ Updated channel {channel.name} to {new_name}")
                    except discord.HTTPException as e:
                        print(f"⚠️ Failed to update {channel.name}: {e}")
                else:
                    print(f"⏱️ Skipped update — channel already set to {new_name}")

@tasks.loop(minutes=5)
async def heartbeat():
    print("❤️ Bot is alive and well.")

# ------------------- SLASH COMMANDS -------------------
@bot.tree.command(name="checknewmovies", description="Check for new movies in Jellyfin and post to the thread.")
async def check_new_movies(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:
        headers = {
            "X-Emby-Token": JELLYFIN_API_KEY
        }
        response = requests.get(f"{JELLYFIN_URL}/emby/Items", params={
            "IncludeItemTypes": "Movie",
            "SortBy": "DateCreated",
            "SortOrder": "Descending",
            "Recursive": "true",
            "Fields": "PrimaryImageAspectRatio",
            "Limit": 3,
            "ParentId": MOVIES_LIBRARY_ID
        }, headers=headers)

        data = response.json()
        new_movies = data.get("Items", [])

        if not new_movies:
            await interaction.followup.send("🎬 No new movies found.")
            return

        thread = await bot.fetch_channel(MOVIE_ALERT_THREAD_ID)

        for movie in new_movies:
            name = movie.get("Name")
            date_created = movie.get("DateCreated", "")
            image_id = movie.get("Id")
            year = movie.get("ProductionYear", "")
            created_dt = parser.parse(date_created).strftime('%b %d, %Y') if date_created else "Unknown"
            poster_url = f"{JELLYFIN_URL}/emby/Items/{image_id}/Images/Primary"

            embed = discord.Embed(
                title=f"🎬 {name} ({year})",
                description=f"Added on **{created_dt}**",
                color=0x00ff99
            )
            embed.set_image(url=poster_url)
            await thread.send(embed=embed)

        await interaction.followup.send("✅ Posted the latest movies.")
    except Exception as e:
        await interaction.followup.send("❌ Something went wrong.")
        print("Error in /checknewmovies:", e)

#TOGGLE TEST COMMAND
@bot.tree.command(name="toggle_test", description="Toggle test mode on or off")
async def toggle_test(interaction: discord.Interaction):
    global TEST_MODE_ENABLED

    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ You don’t have permission to toggle this.", ephemeral=True)
        return

    TEST_MODE_ENABLED = not TEST_MODE_ENABLED

    # Start/Stop the test reminder based on mode
    if TEST_MODE_ENABLED:
        if not test_reminder.is_running():
            test_reminder.start()
    else:
        if test_reminder.is_running():
            test_reminder.cancel()

    status = "ON ✅" if TEST_MODE_ENABLED else "OFF 🛑"
    await interaction.response.send_message(f"🧪 Test mode is now **{status}**", ephemeral=True)

# STATUS COMMAND
@bot.tree.command(name="status", description="Check if test mode is currently active")
async def status_command(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ You don’t have permission to check this.", ephemeral=True)
        return

    msg = "🧪 Test mode is currently **ON** ✅" if TEST_MODE_ENABLED else "🛑 Test mode is currently **OFF**"
    await interaction.response.send_message(msg, ephemeral=True)

# CLEAN COMMAND
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

# SET TIME ZONE COMMAND
@bot.tree.command(name="settimezone", description="Set your timezone via dropdown menu")
async def set_timezone(interaction: discord.Interaction):
    await interaction.response.send_message("🌍 Select your timezone:", view=TimezoneView(), ephemeral=True)
    
# TIME COMAMND
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
        unix_ts = int(dt_utc.timestamp())
    except Exception as e:
        await interaction.response.send_message("❌ Failed to parse time. Try 'June 22 7pm' or 'tomorrow 5pm'", ephemeral=True)
        return

    msg = f"""🕒 **Timestamp Formats**
**Input:** `{time}`
**Unix Timestamp:** `{unix_ts}`

> `<t:{unix_ts}:R>` → <t:{unix_ts}:R>  
> `<t:{unix_ts}:f>` → <t:{unix_ts}:f>  
> `<t:{unix_ts}:F>` → <t:{unix_ts}:F>  
> `<t:{unix_ts}:t>` → <t:{unix_ts}:t>  
> `<t:{unix_ts}:T>` → <t:{unix_ts}:T>  
> `<t:{unix_ts}:d>` → <t:{unix_ts}:d>  
> `<t:{unix_ts}:D>` → <t:{unix_ts}:D>  
"""

    await interaction.response.send_message(msg)

    zones = [
        ("🇺🇸 Pacific", "America/Colorado"),
        ("🇺🇸 Pacific", "America/Florida"),
        ("🇺🇸 Pacific", "America/Los_Angeles"),
        ("🇺🇸 Pacific", "America/Minnesotta"),
        ("🇺🇸 Eastern", "America/New_York"),
        ("🇺🇸 Pacific", "America/Oregon"),
        ("🇬🇧 UK", "Europe/London"),
        ("🇪🇺 Central Europe", "Europe/Berlin"),
        ("🇦🇺 Sydney", "Australia/Sydney")
    ]

    embed = discord.Embed(title="🕒 Time Conversion", description=f"Original: `{time}`", color=0x00ffcc)
    for label, z in zones:
        z_time = dt_utc.astimezone(pytz.timezone(z))
        embed.add_field(name=label, value=z_time.strftime("%A, %B %d • %I:%M %p"), inline=False)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="create_clock_channel", description="Create a locked voice channel that shows current UTC time")
async def create_clock_channel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You need 'Manage Channels' permission.", ephemeral=True)
        return

    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(connect=False)
    }

    existing = discord.utils.get(guild.voice_channels, name__startswith="🕒 UTC:")
    if existing:
        await interaction.response.send_message("⏱️ Clock voice channel already exists.", ephemeral=True)
        return

    channel = await guild.create_voice_channel("🕒 UTC: Loading...", overwrites=overwrites)
    await interaction.response.send_message(f"✅ Clock voice channel created: {channel.mention}", ephemeral=True)

# ------------------- ERROR HANDLING -------------------

def send_discord_alert(message: str):
    if DISCORD_WEBHOOK:
        payload = {"content": f"🚨 Bot crashed: {message}"}
        try:
            requests.post(DISCORD_WEBHOOK, json=payload)
        except Exception as e:
            print("❌ Failed to send crash alert:", e)

async def main():
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("🚨 BOT CRASHED!")
        traceback.print_exc()
        send_discord_alert(str(e))
