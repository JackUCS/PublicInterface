import discord
from discord.ext import commands
from discord import app_commands
import mysql.connector
import os

# --- CONFIG ---
BOT_TOKEN = os.environ["PUBLIC_BOT_TOKEN"]
DB_CONFIG = {
    "host": os.environ["MYSQLHOST"],
    "user": os.environ["MYSQLUSER"],
    "password": os.environ["MYSQLPASSWORD"],
    "database": os.environ["MYSQLDATABASE"],
    "port": int(os.environ.get("MYSQLPORT", 3306))
}

class InterfaceBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Interface Slash Commands Synced")

bot = InterfaceBot()

# --- EXISTING COMMANDS ---

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

@bot.tree.command(name="watchlist", description="See all your current watched keywords.")
async def watchlist(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT keyword FROM monitoring WHERE user_id = %s AND keyword != 'default_setup'", (user_id,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if not rows:
            return await interaction.response.send_message("📋 Your watchlist is empty. Use `/watch` to add items.", ephemeral=True)
        keywords = "\n".join([f"• `{row[0]}`" for row in rows])
        await interaction.response.send_message(f"📋 **Your Watchlist:**\n{keywords}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# --- NEW LOOKUP COMMANDS ---

@bot.tree.command(name="discord", description="Find a Discord user's linked Roblox account")
async def discord_lookup(interaction: discord.Interaction, user: discord.User):
    """Look up Roblox account from Discord user"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT roblox_id, username, confidence FROM roblox_profiles WHERE discord_id = %s", (str(user.id),))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            embed = discord.Embed(title="🔍 Discord → Roblox", color=0x2b2d31)
            embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={row['roblox_id']}&width=420&height=420&format=png")
            embed.add_field(name="Discord User", value=f"{user.mention} (`{user.id}`)", inline=False)
            embed.add_field(name="Roblox Username", value=f"[{row['username']}](https://www.rolimons.com/player/{row['roblox_id']})", inline=False)
            embed.add_field(name="Roblox ID", value=str(row['roblox_id']), inline=True)
            embed.add_field(name="Confidence", value=f"{'🟢' if row['confidence'] >= 3 else '🟡' if row['confidence'] >= 2 else '🔴'} {row['confidence']}", inline=True)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ No Roblox account found for {user.mention}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="roblox", description="Find a Roblox user's linked Discord account")
async def roblox_lookup(interaction: discord.Interaction, username: str):
    """Look up Discord account from Roblox username"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT discord_id, roblox_id, confidence FROM roblox_profiles WHERE LOWER(username) = %s ORDER BY confidence DESC LIMIT 1", (username.lower(),))
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
                embed.add_field(name="Confidence", value=f"{'🟢' if row['confidence'] >= 3 else '🟡' if row['confidence'] >= 2 else '🔴'} {row['confidence']}", inline=True)
                await interaction.response.send_message(embed=embed)
            except:
                await interaction.response.send_message(f"✅ Found Roblox user `{username}` (ID: {row['roblox_id']}), but Discord user left the server.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No Discord account found for Roblox user `{username}`", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

bot.run(BOT_TOKEN)