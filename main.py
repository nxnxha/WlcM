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
RECRUIT_MENTION_RATE = float(os.getenv("RECRUIT_MENTION_RATE", "0.4")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

if not DISCORD_TOKEN or not WELCOME_CHANNEL_ID:
    raise SystemExit("❌ Configure DISCORD_TOKEN et WELCOME_CHANNEL_ID dans Railway > Variables")

# ========= DISCORD =========
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="¤", intents=intents)

# ========= IA PERSONA =========
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
            "T’as fini de provoquer ou on avance ?",
            "Hmm… intéressant, mais je reste Miri, pas ta pote docile."
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
        return "Miri bug un peu, mais je reviens vite. 😶‍🌫️"

# ========= BIENVENUE =========
WELCOME_LINES = [
    "Bienvenue {m} ! T’as trouvé la planque la plus stylée de Discord 😏",
    "Yo {m} 👋 On t’attendait, t’as intérêt à mettre l’ambiance.",
    "{m}, t’es officiellement membre de la team Miri ✨",
    "Hey {m} ! Dépose ton sac, prends un siège et profite.",
    "Salut {m} ! Ici on rigole, on débat et on chill. T’es prêt·e ?",
    "Ravi·e de t’avoir {m} ! 🚀",
    "Ohhh {m} débarque dans la place 🔥",
    "Bienvenue {m}, évite juste de faire le clown sinon tu vas goûter à mes vannes.",
    "Mdr {m} t’as spawn ici, chanceux·se 😎",
    "Yo {m}, prends tes aises, le chaos commence.",
    "Hey {m}, prépare-toi aux blagues nulles et aux débats inutiles 😂",
    "Bienvenue {m} dans le repaire secret de Miri.",
    "Oh {m} 👀 Un nouveau visage, ça fait plaisir.",
    "{m} a rejoint le game 🕹️",
    "Bienvenue {m}, le serveur est un peu bizarre mais tu vas kiffer.",
    "Yo {m} ✨ Mets-toi bien, ici c’est freestyle.",
    "Bien ou quoi {m} ?! Bienvenue chez les zinzins.",
    "Bienvenue {m}, on t’a gardé une place au coin 🔥",
    "Heeey {m} ! Attention je retiens les noms 👀",
    "Oh non… {m} est là 😱 (j’rigole, bienvenue !)",
    "Wsh {m} ! Pose-toi, t’es chez toi.",
    "Tadaaa {m} vient de spawn ✨",
    "Bienvenue {m}, évite juste de spam sinon je deviens méchante 😇",
    "On applaudit {m} qui vient d’arriver 👏",
    "{m}… un de plus dans la secte 😏",
    "Yo {m}, bienvenue dans ce joyeux bazar.",
    "Bienvenue {m}, tu verras, ici c’est comme Netflix mais gratuit.",
    "Salut {m}, t’as signé pour du fun (et quelques trolls).",
    "Bienvenue {m}, accroche-toi ça va secouer 🚀",
    "Oh {m}, j’espère que t’as de l’humour sinon ça va être compliqué."
]

def ticket_line() -> str | None:
    c = []
    if TICKET_GS_CHANNEL_ID: 
        c.append(f"Pour un ticket GS : <#{TICKET_GS_CHANNEL_ID}>")
    if TICKET_RECRUIT_CHANNEL_ID: 
        c.append(f"Pour un ticket Recrutement : <#{TICKET_RECRUIT_CHANNEL_ID}>")
    if not c: return None
    return random.choice(c)

def should_drop_ticket_hint() -> bool:
    return random.random() < RECRUIT_MENTION_RATE

async def send_welcome(member: discord.Member):
    ch = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not isinstance(ch, discord.TextChannel):
        return
    if not ch.permissions_for(member.guild.me).send_messages:
        return

    base = random.choice(WELCOME_LINES).format(m=member.mention)
    extra = ("\n" + ticket_line()) if (should_drop_ticket_hint() and ticket_line()) else ""
    msg = f"{base}{extra}"
    await ch.send(msg)

# ========= EVENTS =========
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"[READY] {bot.user} connecté | {len(synced)} slash cmds")
    except Exception as e:
        print(f"[READY] sync fail: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    await send_welcome(member)

# ========= TEST =========
@app_commands.command(name="welcometest", description="(Admin) Tester un message de bienvenue")
@app_commands.default_permissions(administrator=True)
async def welcometest(interaction: discord.Interaction, member: discord.Member | None = None):
    target = member or interaction.user
    await send_welcome(target)
    await interaction.response.send_message("✅ Message de bienvenue envoyé.", ephemeral=True)

bot.tree.add_command(welcometest)

# ========= REACTIONS IA =========
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    if bot.user and (bot.user in message.mentions or message.reference):
        reply = await ai_reply(message.clean_content)
        await message.reply(reply)
    await bot.process_commands(message)

# ========= RUN =========
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
