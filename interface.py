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

bot.run(BOT_TOKEN)