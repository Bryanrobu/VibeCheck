import os
from datetime import datetime, timedelta
dagen = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
maanden = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]

import discord
from discord import app_commands
from dotenv import load_dotenv

import sqlite3
con = sqlite3.connect("vibeCheck.db")
cur = con.cursor()

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
    cur.execute("CREATE TABLE IF NOT EXISTS checkins(uid, datum, score, beschrijving)")
    cur.execute("CREATE TABLE IF NOT EXISTS memes(naam, afbeelding, kans)")


@bot.tree.command(name="ping", description="Test of Vibecheck werkt")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! Vibecheck is online.")

@bot.tree.command(name="clear", description="Clear je checkins! (tijdelijk voor tests)")
async def clear(interaction: discord.Interaction):
    cur.execute("DELETE FROM checkins WHERE uid = ?", (interaction.user.id,))
    aantal = cur.rowcount
    con.commit()
    await interaction.response.send_message(
        f"Je gegevens zijn verwijderd: {aantal} check-in(s) gewist.",
        ephemeral=True,
    )


@bot.tree.command(name="checkin", description="Laat weten hoe je je voelt")
@app_commands.describe(
    score="Hoe voel je je? 1 = slecht, 10 = top",
    beschrijving="Vertel kort waarom",
)
async def checkin(
    interaction: discord.Interaction,
    score: app_commands.Range[int, 1, 10],
    beschrijving: str,
):
    datum = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO checkins (uid, datum, score, beschrijving) VALUES (?, ?, ?, ?)",
        (interaction.user.id, datum, score, beschrijving),
    )
    con.commit()
    await interaction.response.send_message(
        f"Check-in opgeslagen! Score: {score}/10\n> {beschrijving}",
        ephemeral=True,
    )

@bot.tree.command(name="mijnweek", description="Geeft een overzicht van jou checkins gedurende de week")
async def mijn_week(
    interaction: discord.Interaction
):
    vorigeWeek = (datetime.now() - timedelta(days=7)).isoformat()
    cur.execute(
        "SELECT * FROM checkins WHERE uid = ? AND datum >= ?",
    (interaction.user.id, vorigeWeek),
    )
    results = cur.fetchall()
    if not results:
        await interaction.response.send_message("Je hebt nog geen check-ins gevonden voor deze week.")
        return

    bericht = "Hier is jouw overzicht van deze week:\n"

    for row in results:
        tijd_string = row[1]
        cijfer = row[2]
        reden = row[3]

        dt = datetime.fromisoformat(tijd_string)
        dag_naam = dagen[dt.weekday()]
        maand_naam = maanden[dt.month - 1]
        dag_nummer = dt.day
        tijd = dt.strftime("%H:%M")

        mooie_tijd = f"{dag_naam} {dag_nummer} {maand_naam} om {tijd}"

        bericht += f"- {mooie_tijd} voelde je jezelf {cijfer} omdat: {reden}\n"

    await interaction.response.send_message(bericht, ephemeral=True,)

bot.run(TOKEN)
