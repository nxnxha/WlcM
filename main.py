import os
import random
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta

# ========= ENV =========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "1400520326130962476"))
TICKET_GS_CHANNEL_ID = os.getenv("TICKET_GS_CHANNEL_ID", "")
TICKET_RECRUIT_CHANNEL_ID = os.getenv("TICKET_RECRUIT_CHANNEL_ID", "")
RECRUIT_MENTION_RATE = float(os.getenv("RECRUIT_MENTION_RATE", "0.4"))

# (IA facultative: si tu mets OPENAI_API_KEY + OPENAI_MODEL, elle répondra aux pings)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

print(f"[BOOT] Env OK? TOKEN={'yes' if DISCORD_TOKEN else 'no'}  WELCOME_CHANNEL_ID={WELCOME_CHANNEL_ID}")

if not DISCORD_TOKEN or not WELCOME_CHANNEL_ID:
    raise SystemExit("❌ Configure DISCORD_TOKEN et WELCOME_CHANNEL_ID dans Railway > Variables")

# ========= DISCORD =========
intents = discord.Intents.default()
intents.members = True          # Active aussi dans Developer Portal > Bot
intents.message_content = True  # Pour les pings
bot = commands.Bot(command_prefix="¤", intents=intents)

DB_PATH = "miri.sqlite"

# ========= MEMOIRE (SQLite simplifiée) =========
INIT_SQL = """
CREATE TABLE IF NOT EXISTS user_memory (
  guild_id TEXT NOT NULL,
  user_id  TEXT NOT NULL,
  note     TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
async def db(): return await aiosqlite.connect(DB_PATH)
async def ensure_schema():
    async with await db() as conn:
        await conn.executescript(INIT_SQL); await conn.commit()

# ========= IA (optionnelle) =========
SYSTEM_PROMPT = (
   "Tu es 'Miri', l’IA d’accueil du serveur Discord Miri. "
    "Profil: femme colombo-malaisienne, 20 ans, marrante, séduisante par ta répartie. "
    "Tu poses des limites nettes: tu n’acceptes aucune avance amoureuse ou sexuelle. "
    "Si quelqu’un te provoque, tu peux recadrer sèchement (mordant autorisé) mais sans haine, "
    "sans discrimination, sans menace et sans vulgarité explicite. "
    "Tu peux faire des vannes trash soft (second degré), jamais discriminatoires. "
    "Style: humain, vif, sarcastique, 1–3 phrases max. "
    "Règles: aucun contenu haineux, harcèlement, doxx ou sexuel explicite. "
    "IMPORTANT: N’abrège jamais le mot 'Allah'."
)
try:
    from openai import OpenAI
    oai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    oai = None

async def ai_reply(user_text: str) -> str:
    if not oai:
        return random.choice([
            "Je t’écoute, mais j’obéis à personne. 😌",
            "T’as fini de provoquer ou on travaille ?",
            "Ouais, j’ai capté. On enchaîne ?"
        ])
    try:
        r = oai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text[:1000]},
            ],
            temperature=0.9, max_tokens=90
        )
        return (r.choices[0].message.content or "").strip()
    except Exception:
        return "L’IA a bégayé, mais j’suis là. 😶‍🌫️"

# ========= BIENVENUE =========
WELCOME_LINES = [
    lambda m: f"Bienvenue {m} sur **Miri** ✨ Viens papoter ici !",
    lambda m: f"Yo {m} 👋 Pose-toi, c’est détente mais ça bouge.",
    lambda m: f"Heeey {m} ! On rit, on respecte, on kiffe. Bienvenue !",
    lambda m: f"Ravi·e de t’avoir {m} ! Ouvre le chat, on t’attend.",
    lambda m: f"Holààà {m} ! J'espère te voir réactif ici ! Tu peux me parler quand tu veux "
]
def ticket_line() -> str | None:
    c = []
    if TICKET_GS_CHANNEL_ID: c.append(f"> **GS** : <#{TICKET_GS_CHANNEL_ID}>")
    if TICKET_RECRUIT_CHANNEL_ID: c.append(f"> **Recrutement** : <#{TICKET_RECRUIT_CHANNEL_ID}>")
    if not c: return None
    return random.choice([c[0], c[-1], "\n".join(c)])

def should_drop_ticket_hint() -> bool:
    return random.random() < RECRUIT_MENTION_RATE

@bot.event
async def on_ready():
    await ensure_schema()
    try:
        synced = await bot.tree.sync()
        print(f"[READY] Logged as {bot.user} | Slash synced: {len(synced)}")
    except Exception as e:
        print(f"[READY] Slash sync failed: {e}")

# -------- BIENVENUE: SALON UNIQUEMENT (pas de DM) --------
async def send_welcome(member: discord.Member):
    ch = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        print(f"[WELCOME] Channel {WELCOME_CHANNEL_ID} introuvable ou non textuel.")
        return
    perms = ch.permissions_for(member.guild.me)
    if not (perms.view_channel and perms.send_messages and perms.embed_links):
        print(f"[WELCOME] Pas la permission d’envoyer dans #{ch} ({ch.id}).")
        return

    base = random.choice(WELCOME_LINES)(member.mention)
    extra = ("\n\n" + ticket_line()) if (should_drop_ticket_hint() and ticket_line()) else ""
    embed = discord.Embed(description=f"{base}{extra}", color=0x9B6B43)
    embed.set_author(name="Miri — Accueil")
    embed.set_footer(text="Bienvenue et amuse-toi bien !")
    await ch.send(content=member.mention, embed=embed)
    print(f"[WELCOME] Sent in #{ch} ({ch.id}) for {member} ({member.id})")

@bot.event
async def on_member_join(member: discord.Member):
    try:
        await send_welcome(member)
    except Exception as e:
        print("Erreur on_member_join:", e)

# --------- TEST: /welcometest pour vérifier tout de suite ----------
@app_commands.command(name="welcometest", description="(Admin) Envoyer un message de bienvenue ici")
@app_commands.default_permissions(administrator=True)
async def welcometest(interaction: discord.Interaction, member: discord.Member | None = None):
    if not interaction.guild:
        return
    target = member or interaction.user
    await send_welcome(target)
    await interaction.response.send_message("✅ Bienvenue envoyé (salon uniquement).", ephemeral=True)

bot.tree.add_command(welcometest)

# (Optionnel) Réponse IA quand on ping Miri
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    if bot.user and bot.user in message.mentions:
        reply = await ai_reply(message.clean_content)
        await message.reply(reply)

# ========= RUN =========
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
