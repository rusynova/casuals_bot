import os
import discord
import traceback
import requests
import asyncio
import json
import pytz
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
TIMEZONE_FILE = "user_timezones.json"
current_time = datetime.now(timezone.utc).strftime("%-I:%M%p").lower()

# ------------------- UTILITY FUNCTIONS -------------------

def load_timezones():
    if not os.path.exists(TIMEZONE_FILE):
        return {}
    with open(TIMEZONE_FILE, "r") as f:
        return json.load(f)

def save_timezones(data):
    with open(TIMEZONE_FILE, "w") as f:
        json.dump(data, f, indent=4)

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
    
    # Clear and resync commands for a specific guild
    guild = discord.Object(id=YOUR_GUILD_ID)  # replace with your server's ID
    try:
        await bot.tree.clear_commands(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced commands to guild {guild.id}")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

# ------------------- TASKS -------------------

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
    current_time = datetime.now(timezone.utc).strftime("%-I:%M%p").lower()
    new_name = f"🕒 UTC: {current_time}"

    for guild in bot.guilds:
        for channel in guild.voice_channels:
            if channel.name.startswith("🕒 UTC:"):
                if channel.name != new_name:
                    try:
                        await channel.edit(name=new_name)
                        print(f"✅ Updated channel {channel.name} to {new_name}")
                    except discord.HTTPException as e:
                        print(f"⚠️ Failed to update {channel.name}: {e}")
                else:
                    print(f"⏱️ Skipped update — channel already set to {new_name}")

# ------------------- SLASH COMMANDS -------------------

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

try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    print("🚨 BOT CRASHED!")
    traceback.print_exc()
    send_discord_alert(str(e))
