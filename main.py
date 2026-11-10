import os

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("SERVER_ID")


class Vibecheck(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = Vibecheck()


@bot.event
async def on_ready():
    print(f"{bot.user} is online!")


@bot.tree.command(name="ping", description="Test of Vibecheck werkt")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! Vibecheck is online.")


# Hier komen straks /checkin, /mijnweek en /opkikker

bot.run(TOKEN)
