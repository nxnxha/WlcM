import os
import random
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import datetime
import re

# ========= ENV =========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "1400520326130962476"))
TICKET_GS_CHANNEL_ID = os.getenv("TICKET_GS_CHANNEL_ID", "")
TICKET_RECRUIT_CHANNEL_ID = os.getenv("TICKET_RECRUIT_CHANNEL_ID", "")
RECRUIT_MENTION_RATE = float(os.getenv("RECRUIT_MENTION_RATE", "0.4"))

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
    "Bienvenue {m} dans notre petite safe place.",
    "Yo {m} t’as intérêt à mettre l’ambiance sinon c'est dehoooors.",
    "Oh non....{m} a rejoint, qui l'a invité sérieux ? <:cringe:1417180989775679600>",
    "{m}, t’es officiellement membre de la team Miri deviens vite un staff",
    "Hey {m} ! T'es le bienvenu à condition que tu sois un vrai modo discord.",
    "Salut {m} ! Ici on rigole, on débat et on chill. Parle avec nous et ne soit pas timide !",
    "Ravi·e de t’avoir {m} parmis nous, en espèrant que tu sois pas juste un jnoun de passage.",
    "Ohhh {m} débarque dans le serveur et on peut dire qu'il prend de la place !",
    "Bienvenue {m}",
    "Salem {m} t'as mangé quoi aujourd'hui?",
    "Mais non !!! {m} t’es le nouveau clown du serveur ?? <a:Clown_miri:1402010320683270234>",
    "Bienvenue {m} , on te met au défi de pas être autant inutile que le dernier arrivé.",
    "Yo {m}, prends tes aises, le chaos commence.",
    "Active ton micro {m} et prépare toi à être notre nouveau souffre douleur, soit pas timide hihi.",
    "Hey {m}, prépare-toi aux blagues nulles et aux débats inutiles... ",
    "Bienvenue {m} dans le repaire secret de Miri.",
    "Oh {m} un nouveau visage, ça fait plaisir.",
    "Bienvenue {m}, le serveur est un peu bizarre mais tu vas kiffer.",
    "Bien ou quoi {m} ?! Bienvenue dans l'hôpital psychiatrique Miri.",
    "Bienvenue {m}, on t’a gardé une place au coin !",
    "Heeey {m} ! Attention je vais te surveiller de très près...",
    "Oh non… {m} est là 😱 (j’rigole.. ou pas mais, bienvenue )",
    "T'as deux options ici {m}, soit t'es drôle soit t'es kick. Quel est ton choix?",
    " Bienvenue {m} n'hésites pas à t'inscrire au Casino https://discordapp.com/channels/1382730341944397967/1402211773905375313 et à tous les tabasser !",
    " Ohhhh {m} si tu as plus de 18 ans n'hésites pas à rejoindre https://discordapp.com/channels/1382730341944397967/1400808431941849178 il y aura des events de folies !",
    " Hmmm {m} un gros puant comme on les aime",
    "Si tu clc {m} dehorssssssss !!"
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

# ========= AMBIENT LIMITS =========
AMBIENT_ENABLED = os.getenv("AMBIENT_ENABLED", "true").lower() == "true"
AMBIENT_PROBABILITY = float(os.getenv("AMBIENT_PROBABILITY", "0.15"))
AMBIENT_GLOBAL_COOLDOWN_H = int(os.getenv("AMBIENT_GLOBAL_COOLDOWN_H", "12"))
AMBIENT_CHANNEL_COOLDOWN_MIN = int(os.getenv("AMBIENT_CHANNEL_COOLDOWN_MIN", "45"))
AMBIENT_DAILY_MAX = int(os.getenv("AMBIENT_DAILY_MAX", "3"))

_last_user_reply = {}
_last_ambient_global = None
_last_ambient_channel = {}
_ambient_day_count = {}

def can_ambient_reply(guild_id: int, channel_id: int) -> bool:
    global _last_ambient_global, _last_ambient_channel, _ambient_day_count
    if not AMBIENT_ENABLED:
        return False
    now = datetime.datetime.utcnow()
    today = now.date().isoformat()

    if _last_ambient_global and (now - _last_ambient_global) < datetime.timedelta(hours=AMBIENT_GLOBAL_COOLDOWN_H):
        return False
    if _ambient_day_count.get(today, 0) >= AMBIENT_DAILY_MAX:
        return False
    last_c = _last_ambient_channel.get(channel_id)
    if last_c and (now - last_c) < datetime.timedelta(minutes=AMBIENT_CHANNEL_COOLDOWN_MIN):
        return False

    return random.random() < AMBIENT_PROBABILITY

def mark_ambient_used(channel_id: int):
    global _last_ambient_global, _last_ambient_channel, _ambient_day_count
    now = datetime.datetime.utcnow()
    today = now.date().isoformat()
    _last_ambient_global = now
    _last_ambient_channel[channel_id] = now
    _ambient_day_count[today] = _ambient_day_count.get(today, 0) + 1

# ========= REACTIONS IA =========
USER_COOLDOWN_S = 6

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    # --- est-ce une reply ? ---
    is_reply = (message.type == discord.MessageType.reply) or (message.reference is not None)

    # --- ping explicite tapé dans le contenu (pas le ping auto des replies) ---
    def _explicit_ping(txt: str) -> bool:
        if not bot.user:
            return False
        return (f"<@{bot.user.id}>" in txt) or (f"<@!{bot.user.id}>" in txt)

    has_explicit_ping = _explicit_ping(message.content)

    # --- est-ce que la reply cible un message de Miri ? ---
    is_reply_to_miri = False
    if is_reply and message.reference and getattr(message.reference, "message_id", None):
        ref = getattr(message.reference, "resolved", None)
        if ref is None:
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
            except Exception:
                ref = None
        if ref and ref.author and bot.user and ref.author.id == bot.user.id:
            is_reply_to_miri = True

    # 🔕 ignore toute reply auto à Miri, sauf si ping explicite
    if is_reply_to_miri and not has_explicit_ping:
        await bot.process_commands(message)
        return

    # 📣 Si ping explicite → répondre toujours
    if has_explicit_ping:
        reply = await ai_reply(message.clean_content)
        await message.reply(reply, mention_author=False)
        _last_user_reply[message.author.id] = datetime.datetime.utcnow().timestamp()
        await bot.process_commands(message)
        return

    # --- Mode ambiant (jamais en reply) ---
    now_ts = datetime.datetime.utcnow().timestamp()
    if is_reply:
        await bot.process_commands(message)
        return

    if _last_user_reply.get(message.author.id, 0) + USER_COOLDOWN_S > now_ts:
        await bot.process_commands(message)
        return

    def _is_short_question(text: str) -> bool:
        t = text.strip()
        return len(t) <= 120 and t.endswith("?")

    def _talks_about_miri(text: str) -> bool:
        return bool(re.search(r"\bmiri\b", text.lower()))

    ambient_trigger = _talks_about_miri(message.content) or _is_short_question(message.content)

    if ambient_trigger and can_ambient_reply(message.guild.id, message.channel.id):
        _last_user_reply[message.author.id] = now_ts
        reply = await ai_reply(message.clean_content)
        await message.reply(reply, mention_author=False)
        mark_ambient_used(message.channel.id)

    await bot.process_commands(message)

# ========= RUN =========
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
