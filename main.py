import os
import random
from datetime import datetime, timedelta
dagen = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
maanden = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]

from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

import sqlite3
con = sqlite3.connect("vibeCheck.db")
cur = con.cursor()

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("SERVER_ID")

IMG_DIR = Path(__file__).parent / "img"
EXTENSIES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# naam: (kans in % per niveau, kleur)
ZELDZAAMHEID = {
    "gewoon": (60, discord.Color.green()),
    "zeldzaam": (25, discord.Color.blue()),
    "episch": (12, discord.Color.purple()),
    "legendarisch": (3, discord.Color.gold()),
    "mythisch": (0.1, discord.Color.red())
}
STANDAARD_NIVEAU = "gewoon"

# bestandsnaam zonder extensie: niveau
# Let op: bij elke start worden deze waarden in de database gezet.
MEME_NIVEAUS = {
    "biertje": "gewoon",
    "mooi": "zeldzaam",
    "schaap": "legendarisch",
    "man-in-de-auto": "gewoon",
    "man-bij-de-container": "gewoon",
    "maak-je-ernie-druk": "zeldzaam",
    "man-man-man": "episch",
    "applausje-of-wa": "legendarisch",
    "oude-koeien-uit-de-sloot": "episch",
    "belgie-zuid-nederland": "gewoon",
    "interview-reactie": "zeldzaam",
    "boze-jongen": "gewoon",
    "broccoli-man": "zeldzaam",
    "at5-interview": "episch",
    "pelle-is-aan-het-maaien": "legendarisch",
}


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


def ensure_collection_schema():
    primary_key = [
        column[1]
        for column in sorted(
            (column for column in cur.execute("PRAGMA table_info(collectie)") if column[5]),
            key=lambda column: column[5],
        )
    ]
    if primary_key == ["uid", "meme"]:
        return

    con.commit()
    with con:
        cur.execute("BEGIN")
        cur.execute(
            """CREATE TABLE collectie_new (
                uid, meme, aantal, PRIMARY KEY (uid, meme)
            )"""
        )
        cur.execute(
            """INSERT INTO collectie_new (uid, meme, aantal)
               SELECT uid, meme, SUM(aantal) FROM collectie GROUP BY uid, meme"""
        )
        cur.execute("DROP TABLE collectie")
        cur.execute("ALTER TABLE collectie_new RENAME TO collectie")


def sync_memes():
    # nieuwe plaatjes in img/ toevoegen
    bekend = {r[0] for r in cur.execute("SELECT afbeelding FROM memes").fetchall()}
    for pad in IMG_DIR.iterdir():
        if pad.suffix.lower() in EXTENSIES and pad.name not in bekend:
            cur.execute(
                "INSERT INTO memes (naam, afbeelding, kans) VALUES (?, ?, ?)",
                (pad.stem, pad.name, STANDAARD_NIVEAU),
            )

    # oude getallen (bijv. 10) of onbekende waarden terugzetten naar gewoon
    geldig = tuple(ZELDZAAMHEID)
    cur.execute(
        f"UPDATE memes SET kans = ? WHERE kans NOT IN ({','.join('?' * len(geldig))})",
        (STANDAARD_NIVEAU, *geldig),
    )

    # niveaus uit MEME_NIVEAUS toepassen
    for naam, niveau in MEME_NIVEAUS.items():
        cur.execute("UPDATE memes SET kans = ? WHERE naam = ?", (niveau, naam))

    con.commit()


@bot.event
async def on_ready():
    print(f"{bot.user} is online!")
    cur.execute("CREATE TABLE IF NOT EXISTS checkins(uid, datum, score, beschrijving)")
    cur.execute("CREATE TABLE IF NOT EXISTS memes(naam, afbeelding, kans)")
    cur.execute("CREATE TABLE IF NOT EXISTS collectie(uid, meme, aantal, PRIMARY KEY (uid, meme))")
    ensure_collection_schema()
    sync_memes()

@bot.tree.command(name="ping", description="Test of Vibecheck werkt")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! Vibecheck is online.")

@bot.tree.command(name="clear", description="Clear je checkins! (tijdelijk voor tests)")
async def clear(interaction: discord.Interaction):
    cur.execute("DELETE FROM checkins WHERE uid = ?", (interaction.user.id,))
    aantal = cur.rowcount
    con.commit()
    cur.execute("DELETE FROM collectie WHERE uid = ?", (interaction.user.id,))
    aantal2 = cur.rowcount
    con.commit()
    await interaction.response.send_message(
        f"Je gegevens zijn verwijderd: {aantal} check-in(s) gewist, en: {aantal2} memes gewist.",
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



@bot.tree.command(name="opkikker", description="Rol een willekeurige meme!")
async def roll(interaction: discord.Interaction):
    rijen = cur.execute("SELECT naam, afbeelding, kans FROM memes").fetchall()
    memes = [m for m in rijen if (IMG_DIR / m[1]).exists()]

    if not memes:
        await interaction.response.send_message(
            "Er staan nog geen memes in de img-map.", ephemeral=True
        )
        return

    # 1. groepeer de memes per niveau (de opgeslagen naam)
    per_niveau = {}
    for m in memes:
        per_niveau.setdefault(m[2], []).append(m)

    # 2. kies eerst een niveau, op basis van de percentages
    niveaus = list(per_niveau)
    niveau = random.choices(
        niveaus, weights=[ZELDZAAMHEID[n][0] for n in niveaus], k=1
    )[0]

    # 3. kies dan een meme binnen dat niveau
    naam, bestand, _ = random.choice(per_niveau[niveau])

    totaal = sum(ZELDZAAMHEID[n][0] for n in niveaus)
    procent = ZELDZAAMHEID[niveau][0] / totaal * 100 / len(per_niveau[niveau])
    kleur = ZELDZAAMHEID[niveau][1]
        # 4. meteen in de collectie zetten
    bestaand = cur.execute(
        "SELECT 1 FROM collectie WHERE uid = ? AND meme = ?",
        (interaction.user.id, naam),
    ).fetchone()
    nieuw = bestaand is None

    cur.execute(
        """INSERT INTO collectie (uid, meme, aantal) VALUES (?, ?, 1)
           ON CONFLICT(uid, meme) DO UPDATE SET aantal = aantal + 1""",
        (interaction.user.id, naam),
    )
    con.commit()

    pad = IMG_DIR / bestand
    veilige_naam = f"meme{pad.suffix}"
    file = discord.File(pad, filename=veilige_naam)

    embed = discord.Embed(
        title=naam,
        description=f"**{niveau.capitalize()}** · kans {procent:.1f}%",
        color=kleur,
    )
    embed.set_image(url=f"attachment://{veilige_naam}")

    await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
   
@bot.tree.command(name="collectie", description="Bekijk welke memes je hebt verzameld")
async def collectie(interaction: discord.Interaction):
    alle = cur.execute("SELECT naam, kans FROM memes").fetchall()
    bezit = dict(
        cur.execute(
            "SELECT meme, aantal FROM collectie WHERE uid = ?",
            (interaction.user.id,),
        ).fetchall()
    )

    # zeldzaamste bovenaan
    volgorde = list(ZELDZAAMHEID)
    alle.sort(key=lambda m: volgorde.index(m[1]) if m[1] in volgorde else 0, reverse=True)

    regels = []
    for naam, niveau in alle:
        if naam in bezit:
            regels.append(f"✅ **{naam}** · {niveau.capitalize()} · x{bezit[naam]}")
        else:
            regels.append(f"❓ ??? · {niveau.capitalize()}")

    verzameld = sum(1 for naam, _ in alle if naam in bezit)
    totaal_rolls = sum(bezit.get(naam, 0) for naam, _ in alle)

    embed = discord.Embed(
        title=f"Collectie van {interaction.user.display_name}",
        description="\n".join(regels) or "Er zijn nog geen memes.",
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"{verzameld}/{len(alle)} verzameld · {totaal_rolls} keer gerold")

    await interaction.response.send_message(embed=embed)

bot.run(TOKEN)
