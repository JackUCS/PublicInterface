import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector
import os
import datetime
import traceback

# --- CONFIG ---
BOT_TOKEN = os.environ["PUBLIC_BOT_TOKEN"]
DB_CONFIG = {
    "host": os.environ["MYSQLHOST"],
    "user": os.environ["MYSQLUSER"],
    "password": os.environ["MYSQLPASSWORD"],
    "database": os.environ["MYSQLDATABASE"],
    "port": int(os.environ.get("MYSQLPORT", 3306)),
    "connection_timeout": 5
}

class InterfaceBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        try:
            await self.tree.sync()
            print("✅ Interface Slash Commands Synced Successfully!")
            print(f"✅ Bot is in {len(self.guilds)} guilds")
        except Exception as e:
            print(f"❌ Failed to sync commands: {e}")
            traceback.print_exc()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        print(f"✅ Connected to {len(self.guilds)} guilds")

bot = InterfaceBot()

# --- SETUP COMMANDS ---

@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! Latency: `{round(bot.latency * 1000)}ms`", ephemeral=True)

@bot.tree.command(name="invite", description="Get the bot invite link")
async def invite(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🔗 **Invite me:** https://discord.com/oauth2/authorize?client_id={bot.user.id}&scope=bot&permissions=0",
        ephemeral=True
    )

@bot.tree.command(name="help", description="Show all available commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📚 Kotsa Monitor - Help", color=0x2b2d31)
    embed.add_field(name="🔧 Setup", value="`/setwebhook` - Save your webhook\n`/watch` - Add keyword\n`/watchmany` - Add multiple keywords\n`/unwatch` - Remove keyword\n`/unwatchall` - Remove all\n`/watchlist` - View your keywords", inline=False)
    embed.add_field(name="🔍 Lookup", value="`/discord @user` - Find Roblox from Discord\n`/roblox username` - Find Discord from Roblox\n`/lookup query` - Smart auto-detect", inline=False)
    embed.add_field(name="📊 Stats", value="`/topitems` - Most watched items\n`/topusers` - Users with most keywords\n`/profilecount` - Database stats\n`/itemsearch` - Who watches an item", inline=False)
    embed.add_field(name="ℹ️ Other", value="`/ping` - Bot latency\n`/invite` - Invite link\n`/about` - Bot info", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="about", description="About this bot")
async def about(interaction: discord.Interaction):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT user_id) FROM monitoring WHERE keyword != 'default_setup'")
        watchers = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM monitoring WHERE keyword != 'default_setup'")
        keywords = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM roblox_profiles")
        profiles = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        embed = discord.Embed(title="🤖 Kotsa Monitor Bot", color=0x2b2d31)
        embed.add_field(name="Purpose", value="Real-time keyword alerts for Roblox limited item trading across multiple Discord servers.", inline=False)
        embed.add_field(name="Users", value=f"`{watchers}` watchers", inline=True)
        embed.add_field(name="Keywords", value=f"`{keywords}` tracked", inline=True)
        embed.add_field(name="Profiles", value=f"`{profiles}` linked", inline=True)
        embed.set_footer(text="Made for the Kotsa trading community")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ DB Error: {e}", ephemeral=True)

# --- WEBHOOK & KEYWORD MANAGEMENT ---

@bot.tree.command(name="setwebhook", description="Save your webhook URL for alerts.")
async def setwebhook(interaction: discord.Interaction, webhook: str):
    if "discord.com/api/webhooks/" not in webhook:
        return await interaction.response.send_message("❌ Invalid Webhook URL!", ephemeral=True)
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        sql = "INSERT INTO monitoring (user_id, keyword, webhook_url) VALUES (%s, 'default_setup', %s) ON DUPLICATE KEY UPDATE webhook_url = %s"
        cur.execute(sql, (str(interaction.user.id), webhook, webhook))
        conn.commit()
        cur.close()
        conn.close()
        await interaction.response.send_message("✅ Webhook saved! Now use `/watch` to add items.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ DB Error: {e}", ephemeral=True)

@bot.tree.command(name="watch", description="Add an item keyword to your watchlist.")
async def watch(interaction: discord.Interaction, keyword: str):
    user_id = str(interaction.user.id)
    kw = keyword.lower().strip()
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT webhook_url FROM monitoring WHERE user_id = %s LIMIT 1", (user_id,))
        res = cur.fetchone()
        if not res:
            cur.close()
            conn.close()
            return await interaction.response.send_message("❌ Use `/setwebhook` first!", ephemeral=True)
        webhook = res['webhook_url']
        sql = "INSERT INTO monitoring (user_id, keyword, webhook_url) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE webhook_url = %s"
        cur.execute(sql, (user_id, kw, webhook, webhook))
        conn.commit()
        cur.close()
        conn.close()
        await interaction.response.send_message(f"✅ Now watching for: `{kw}`", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="watchmany", description="Add multiple keywords at once (comma-separated)")
async def watchmany(interaction: discord.Interaction, keywords: str):
    user_id = str(interaction.user.id)
    kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]
    if not kw_list:
        return await interaction.response.send_message("❌ Please provide at least one keyword.", ephemeral=True)
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT webhook_url FROM monitoring WHERE user_id = %s LIMIT 1", (user_id,))
        res = cur.fetchone()
        if not res:
            cur.close()
            conn.close()
            return await interaction.response.send_message("❌ Use `/setwebhook` first!", ephemeral=True)
        webhook = res['webhook_url']
        
        added = []
        for kw in kw_list:
            sql = "INSERT INTO monitoring (user_id, keyword, webhook_url) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE webhook_url = %s"
            cur.execute(sql, (user_id, kw, webhook, webhook))
            added.append(kw)
        conn.commit()
        cur.close()
        conn.close()
        
        await interaction.response.send_message(f"✅ Added {len(added)} keywords: {', '.join(['`' + k + '`' for k in added])}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="unwatch", description="Remove a keyword from your watchlist.")
async def unwatch(interaction: discord.Interaction, keyword: str):
    user_id = str(interaction.user.id)
    kw = keyword.lower().strip()
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("DELETE FROM monitoring WHERE user_id = %s AND keyword = %s", (user_id, kw))
        affected = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        if affected:
            await interaction.response.send_message(f"✅ Removed `{kw}` from your watchlist.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ `{kw}` wasn't in your watchlist.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="unwatchall", description="Remove ALL keywords from your watchlist.")
async def unwatchall(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("DELETE FROM monitoring WHERE user_id = %s AND keyword != 'default_setup'", (user_id,))
        affected = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        await interaction.response.send_message(f"✅ Removed {affected} keyword(s) from your watchlist.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="watchlist", description="See all your current watched keywords.")
async def watchlist(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT keyword FROM monitoring WHERE user_id = %s AND keyword != 'default_setup' ORDER BY keyword", (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if not rows:
            return await interaction.response.send_message("📋 Your watchlist is empty. Use `/watch` to add items.", ephemeral=True)
        
        keywords = [row[0] for row in rows]
        kw_text = "\n".join([f"• `{kw}`" for kw in keywords[:20]])
        msg = f"📋 **Your Watchlist ({len(keywords)} items):**\n{kw_text}"
        if len(keywords) > 20:
            msg += f"\n... and {len(keywords) - 20} more"
        await interaction.response.send_message(msg, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# --- LOOKUP COMMANDS ---

@bot.tree.command(name="discord", description="Find a Discord user's linked Roblox account")
async def discord_lookup(interaction: discord.Interaction, user: discord.User):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT roblox_id, username, confidence, updated_at FROM roblox_profiles WHERE discord_id = %s", (str(user.id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            embed = discord.Embed(title="🔍 Discord → Roblox", color=0x2b2d31)
            embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={row['roblox_id']}&width=420&height=420&format=png")
            embed.add_field(name="Discord User", value=f"{user.mention} (`{user.id}`)", inline=False)
            embed.add_field(name="Roblox Username", value=f"[{row['username']}](https://www.rolimons.com/player/{row['roblox_id']})", inline=False)
            embed.add_field(name="Roblox ID", value=str(row['roblox_id']), inline=True)
            embed.add_field(name="Confidence", value=f"{'🟢' if row['confidence'] >= 3 else '🟡' if row['confidence'] >= 2 else '🔴'} {row['confidence']}/5", inline=True)
            if row['updated_at']:
                embed.set_footer(text=f"Last updated: {row['updated_at']}")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ No Roblox account found for {user.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="roblox", description="Find a Roblox user's linked Discord account")
async def roblox_lookup(interaction: discord.Interaction, username: str):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT discord_id, roblox_id, confidence, updated_at FROM roblox_profiles WHERE LOWER(username) = %s ORDER BY confidence DESC LIMIT 1", (username.lower(),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            try:
                discord_user = await bot.fetch_user(int(row['discord_id']))
                embed = discord.Embed(title="🔍 Roblox → Discord", color=0x2b2d31)
                embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={row['roblox_id']}&width=420&height=420&format=png")
                embed.add_field(name="Roblox Username", value=f"[{username}](https://www.rolimons.com/player/{row['roblox_id']})", inline=False)
                embed.add_field(name="Roblox ID", value=str(row['roblox_id']), inline=True)
                embed.add_field(name="Discord User", value=f"{discord_user.mention} (`{discord_user.id}`)", inline=False)
                embed.add_field(name="Confidence", value=f"{'🟢' if row['confidence'] >= 3 else '🟡' if row['confidence'] >= 2 else '🔴'} {row['confidence']}/5", inline=True)
                if row['updated_at']:
                    embed.set_footer(text=f"Last updated: {row['updated_at']}")
                await interaction.response.send_message(embed=embed)
            except:
                await interaction.response.send_message(f"✅ Found Roblox user `{username}` (ID: {row['roblox_id']}), but Discord user not reachable.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No Discord account found for Roblox user `{username}`", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="lookup", description="Smart lookup - auto-detects Discord ID or Roblox username")
async def smart_lookup(interaction: discord.Interaction, query: str):
    if query.isdigit():
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT roblox_id, username, confidence FROM roblox_profiles WHERE discord_id = %s", (query,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                try:
                    user = await bot.fetch_user(int(query))
                    embed = discord.Embed(title="🔍 Discord → Roblox", color=0x2b2d31)
                    embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={row['roblox_id']}&width=420&height=420&format=png")
                    embed.add_field(name="Discord", value=f"{user.mention} (`{query}`)", inline=False)
                    embed.add_field(name="Roblox", value=f"[{row['username']}](https://www.rolimons.com/player/{row['roblox_id']})", inline=False)
                    embed.add_field(name="Confidence", value=f"{'🟢' if row['confidence'] >= 3 else '🟡' if row['confidence'] >= 2 else '🔴'} {row['confidence']}/5", inline=True)
                    return await interaction.response.send_message(embed=embed)
                except:
                    return await interaction.response.send_message(f"Found Roblox user `{row['username']}` but Discord user not reachable.", ephemeral=True)
        except:
            pass
    else:
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT discord_id, roblox_id, confidence FROM roblox_profiles WHERE LOWER(username) = %s ORDER BY confidence DESC LIMIT 1", (query.lower(),))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                try:
                    discord_user = await bot.fetch_user(int(row['discord_id']))
                    embed = discord.Embed(title="🔍 Roblox → Discord", color=0x2b2d31)
                    embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={row['roblox_id']}&width=420&height=420&format=png")
                    embed.add_field(name="Roblox", value=f"[{query}](https://www.rolimons.com/player/{row['roblox_id']})", inline=False)
                    embed.add_field(name="Discord", value=f"{discord_user.mention} (`{row['discord_id']}`)", inline=False)
                    embed.add_field(name="Confidence", value=f"{'🟢' if row['confidence'] >= 3 else '🟡' if row['confidence'] >= 2 else '🔴'} {row['confidence']}/5", inline=True)
                    return await interaction.response.send_message(embed=embed)
                except:
                    return await interaction.response.send_message(f"Found Roblox user `{query}` but Discord user not reachable.", ephemeral=True)
        except:
            pass
    
    await interaction.response.send_message(f"❌ No results for `{query}`", ephemeral=True)

# --- STATS COMMANDS ---

@bot.tree.command(name="topitems", description="Show most watched items")
async def topitems(interaction: discord.Interaction):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT keyword, COUNT(*) as count FROM monitoring WHERE keyword != 'default_setup' GROUP BY keyword ORDER BY count DESC LIMIT 10")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if not rows:
            return await interaction.response.send_message("No keywords being watched yet!", ephemeral=True)
        
        embed = discord.Embed(title="📊 Top 10 Watched Items", color=0x2b2d31)
        items = "\n".join([f"**{i+1}.** `{row[0]}` — {row[1]} watchers" for i, row in enumerate(rows)])
        embed.add_field(name="Items", value=items, inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="topusers", description="Show users with most keywords")
async def topusers(interaction: discord.Interaction):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT user_id, COUNT(*) as count FROM monitoring WHERE keyword != 'default_setup' GROUP BY user_id ORDER BY count DESC LIMIT 10")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if not rows:
            return await interaction.response.send_message("No users tracking keywords yet!", ephemeral=True)
        
        embed = discord.Embed(title="📊 Top 10 Keyword Watchers", color=0x2b2d31)
        for i, row in enumerate(rows):
            try:
                user = await bot.fetch_user(int(row[0]))
                name = user.name
            except:
                name = f"User {row[0]}"
            embed.add_field(name=f"{i+1}. {name}", value=f"`{row[1]}` keywords", inline=True)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="profilecount", description="Show total linked profiles in database")
async def profilecount(interaction: discord.Interaction):
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM roblox_profiles")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM roblox_profiles WHERE confidence >= 5")
        verified = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM roblox_profiles WHERE confidence >= 3")
        high = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM roblox_profiles WHERE confidence = 1")
        low = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        embed = discord.Embed(title="📊 Profile Database Stats", color=0x2b2d31)
        embed.add_field(name="Total Profiles", value=f"`{total}`", inline=True)
        embed.add_field(name="Verified (≥5)", value=f"`{verified}`", inline=True)
        embed.add_field(name="High Conf (≥3)", value=f"`{high}`", inline=True)
        embed.add_field(name="Low Conf (1)", value=f"`{low}`", inline=True)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="itemsearch", description="Search for users watching a specific keyword")
async def itemsearch(interaction: discord.Interaction, keyword: str):
    kw = keyword.lower().strip()
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM monitoring WHERE keyword = %s", (kw,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        if not rows:
            return await interaction.response.send_message(f"📊 No one is watching `{kw}`", ephemeral=True)
        
        await interaction.response.send_message(f"📊 **{len(rows)} user(s)** watching `{kw}`", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# --- ERROR HANDLER ---

@bot.event
async def on_command_error(interaction: discord.Interaction, error):
    print(f"❌ Command error: {error}")
    traceback.print_exc()

# Boot with retry logic
import time
max_retries = 3
for attempt in range(max_retries):
    try:
        print(f"🚀 Attempting to start bot (attempt {attempt + 1}/{max_retries})...")
        bot.run(BOT_TOKEN)
    except Exception as e:
        print(f"❌ Bot crashed (attempt {attempt + 1}): {e}")
        traceback.print_exc()
        if attempt < max_retries - 1:
            wait = 5 * (attempt + 1)
            print(f"⏳ Retrying in {wait} seconds...")
            time.sleep(wait)