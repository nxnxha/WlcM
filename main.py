import os
import random
import asyncio
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from datetime import timedelta

# ====== ENV ======
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID", "0"))
TICKET_GS_CHANNEL_ID = os.getenv("TICKET_GS_CHANNEL_ID", "")
TICKET_RECRUIT_CHANNEL_ID = os.getenv("TICKET_RECRUIT_CHANNEL_ID", "")
RECRUIT_MENTION_RATE = float(os.getenv("RECRUIT_MENTION_RATE", "0.4"))

BANTER_ENABLED = os.getenv("BANTER_ENABLED", "true").lower() == "true"
BANTER_COOLDOWN_SECONDS = int(os.getenv("BANTER_COOLDOWN_SECONDS", "120"))
BANTER_PROBABILITY = float(os.getenv("BANTER_PROBABILITY", "0.05"))

# Ping-banter exceptionnel (avec ping)
QUIET_WINDOW_MIN = int(os.getenv("QUIET_WINDOW_MIN", "30"))
QUIET_MAX_MSGS_IN_WINDOW = int(os.getenv("QUIET_MAX_MSGS_IN_WINDOW", "5"))
PING_BANTER_GLOBAL_COOLDOWN_H = int(os.getenv("PING_BANTER_GLOBAL_COOLDOWN_H", "36"))
PING_BANTER_USER_COOLDOWN_D = int(os.getenv("PING_BANTER_USER_COOLDOWN_D", "7"))

if not DISCORD_TOKEN or not WELCOME_CHANNEL_ID:
    raise SystemExit("Configure DISCORD_TOKEN et WELCOME_CHANNEL_ID dans .env")

# ====== DISCORD CLIENT ======
intents = discord.Intents.default()
intents.members = True           # on_member_join (activer privileged intent côté portail)
intents.message_content = True   # pour réagir aux pings/réponses
bot = commands.Bot(command_prefix="¤", intents=intents)

DB_PATH = "miri.sqlite"

# ====== PERSONA IA ======
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

# ====== OPENAI ======
try:
    from openai import OpenAI
    oai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    oai = None

async def ai_complete(messages, max_tokens=120, temperature=0.9):
    if not oai:
        # Fallback local si pas de clé
        return random.choice([
            "Je t’écoute, mais j’obéis à personne. 😌",
            "Calme-toi, respire… et reformule sans provocation.",
            "Je prends note. Et maintenant, on avance ?"
        ])
    try:
        resp = oai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            presence_penalty=0.3,
            frequency_penalty=0.2
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return "L’IA éternue… Je reviens avec un cerveau tout neuf. 😶‍🌫️"

# ====== MÉMOIRE (SQLite) ======
INIT_SQL = """
CREATE TABLE IF NOT EXISTS user_memory (
  guild_id TEXT NOT NULL,
  user_id  TEXT NOT NULL,
  note     TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_stats (
  guild_id TEXT NOT NULL,
  user_id  TEXT NOT NULL,
  provocations INTEGER DEFAULT 0,
  last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS whitelist_users (
  guild_id TEXT NOT NULL,
  user_id  TEXT NOT NULL,
  PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS whitelist_roles (
  guild_id TEXT NOT NULL,
  role_id  TEXT NOT NULL,
  PRIMARY KEY (guild_id, role_id)
);

CREATE TABLE IF NOT EXISTS ping_banter (
  guild_id TEXT NOT NULL,
  target_id TEXT NOT NULL, -- "GLOBAL" ou user_id ciblé
  last_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (guild_id, target_id)
);
"""

async def db():
    return await aiosqlite.connect(DB_PATH)

async def ensure_schema():
    async with await db() as conn:
        await conn.executescript(INIT_SQL)
        await conn.commit()

async def add_note(guild_id: int, user_id: int, note: str):
    async with await db() as conn:
        await conn.execute(
            "INSERT INTO user_memory (guild_id, user_id, note) VALUES (?, ?, ?)",
            (str(guild_id), str(user_id), note[:400])
        )
        await conn.commit()

async def get_notes(guild_id: int, user_id: int, limit: int = 8):
    async with await db() as conn:
        cur = await conn.execute(
            "SELECT note FROM user_memory WHERE guild_id=? AND user_id=? "
            "ORDER BY created_at DESC LIMIT ?",
            (str(guild_id), str(user_id), limit)
        )
        rows = await cur.fetchall()
    return [r[0] for r in rows]

async def bump_seen(guild_id: int, user_id: int, provoked: bool = False):
    async with await db() as conn:
        await conn.execute(
            "INSERT INTO user_stats (guild_id, user_id, provocations) VALUES (?, ?, 0) "
            "ON CONFLICT(guild_id, user_id) DO NOTHING",
            (str(guild_id), str(user_id))
        )
        if provoked:
            await conn.execute(
                "UPDATE user_stats SET provocations=provocations+1, last_seen=CURRENT_TIMESTAMP "
                "WHERE guild_id=? AND user_id=?",
                (str(guild_id), str(user_id))
            )
        else:
            await conn.execute(
                "UPDATE user_stats SET last_seen=CURRENT_TIMESTAMP "
                "WHERE guild_id=? AND user_id=?",
                (str(guild_id), str(user_id))
            )
        await conn.commit()

async def is_user_wl(guild_id: int, user_id: int) -> bool:
    async with await db() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM whitelist_users WHERE guild_id=? AND user_id=?",
            (str(guild_id), str(user_id))
        )
        u = await cur.fetchone()
        return bool(u)

async def is_any_role_wl(guild_id: int, role_ids: list[int]) -> bool:
    if not role_ids:
        return False
    qmarks = ",".join("?" for _ in role_ids)
    async with await db() as conn:
        cur = await conn.execute(
            f"SELECT 1 FROM whitelist_roles WHERE guild_id=? AND role_id IN ({qmarks})",
            (str(guild_id), *map(str, role_ids))
        )
        r = await cur.fetchone()
        return bool(r)

# ping_banter timestamps
async def _get_ping_ts(guild_id: int, target_id: str):
    async with await db() as conn:
        cur = await conn.execute(
            "SELECT last_ts FROM ping_banter WHERE guild_id=? AND target_id=?",
            (str(guild_id), target_id)
        )
        row = await cur.fetchone()
        return row[0] if row else None

async def _set_ping_ts(guild_id: int, target_id: str):
    async with await db() as conn:
        await conn.execute(
            "INSERT INTO ping_banter (guild_id, target_id, last_ts) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(guild_id, target_id) DO UPDATE SET last_ts=CURRENT_TIMESTAMP",
            (str(guild_id), target_id)
        )
        await conn.commit()

# ====== LOGIQUE PING ======
async def can_requester_authorize_ping(interaction: discord.Interaction) -> bool:
    # Seuls users/roles whitelisted peuvent déclencher un ping via /miri_ping
    if not interaction.guild or not interaction.user:
        return False
    if await is_user_wl(interaction.guild.id, interaction.user.id):
        return True
    user_role_ids = [r.id for r in getattr(interaction.user, "roles", []) if r.name != "@everyone"]
    if await is_any_role_wl(interaction.guild.id, user_role_ids):
        return True
    return False

# ====== TEXTES ======
WELCOME_LINES = [
    lambda m: f"Bienvenue {m} sur **Miri** ✨ Je suis Miri : marrante, piquante et protectrice. Viens papoter !",
    lambda m: f"Yo {m} 👋 Ici c’est **Miri**. On rit, on bosse, on respecte. Installe-toi !",
    lambda m: f"Heeey {m} ! Humour oui, avances non. On garde la vibe clean et on s’amuse. ✨",
    lambda m: f"Ravi·e de t’avoir {m} ! Je veille — quand c’est carré, tout est plus fun."
]

def ticket_line() -> str | None:
    has_gs = bool(TICKET_GS_CHANNEL_ID)
    has_rec = bool(TICKET_RECRUIT_CHANNEL_ID)
    if not (has_gs or has_rec):
        return None
    candidates = []
    if has_gs:
        candidates.append(f"> Besoin **GS** ? Ouvre un ticket : <#{TICKET_GS_CHANNEL_ID}>")
    if has_rec:
        candidates.append(f"> Curieux du **staff** ? Ticket recrutement : <#{TICKET_RECRUIT_CHANNEL_ID}>")
    if len(candidates) == 1:
        return candidates[0]
    return random.choice([candidates[0], candidates[1], "\\n".join(candidates)])

def should_drop_ticket_hint() -> bool:
    return random.random() < RECRUIT_MENTION_RATE

# ====== COOLDOWNS ======
mention_cd = {}
reply_cd = {}
banter_cd = {}
COOLDOWN_SECONDS = 10

def hit_cd(cd_map: dict, key: int, seconds: int) -> bool:
    now = discord.utils.utcnow().timestamp()
    last = cd_map.get(key, 0)
    if now - last >= seconds:
        cd_map[key] = now
        return True
    return False

# ====== IA CONTEXTE ======
async def build_context_messages(guild: discord.Guild, user: discord.abc.User, user_text: str, tone: str):
    # tone: "normal" | "angry" | "banter"
    notes = await get_notes(guild.id, user.id, limit=6)
    notes_text = "\\n".join(f"- {n}" for n in notes) if notes else "Aucune note."
    style_line = {
        "normal": "Réponds marrante/taquine, bienveillante mais avec du caractère.",
        "angry": "Réponds sèche et mordante (sans haine, ni menace). Recadre fermement.",
        "banter": "Fais une vanne piquante (trash soft), courte (2 phrases max), jamais discriminatoire."
    }[tone]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                f"Mémoire sur {user}: \\n{notes_text}\\n"
                f"Mode: {tone}. {style_line}\\n"
                "Interdits: haine, menaces, contenu sexuel explicite, doxx."
            )
        },
        {"role": "user", "content": user_text[:1000]}
    ]
    return messages

async def ai_reply(user_msg: str, guild: discord.Guild, author: discord.abc.User, tone: str = "normal"):
    msgs = await build_context_messages(guild, author, user_msg, tone)
    return await ai_complete(msgs, max_tokens=120, temperature=0.9)

# ====== SALON CALME & COOLDOWNS PING-BANTER ======
async def channel_is_quiet(channel: discord.TextChannel) -> bool:
    """True si peu d’activité récente."""
    now = discord.utils.utcnow()
    cutoff = now - timedelta(minutes=QUIET_WINDOW_MIN)
    count_recent = 0
    try:
        async for msg in channel.history(limit=50, oldest_first=False):
            if msg.created_at and msg.created_at > cutoff:
                count_recent += 1
            if count_recent > QUIET_MAX_MSGS_IN_WINDOW:
                return False
        return True
    except Exception:
        return False

async def can_ping_banter(guild: discord.Guild, target_user_id: int) -> bool:
    now = discord.utils.utcnow()

    # Global CD
    last_global = await _get_ping_ts(guild.id, "GLOBAL")
    if last_global:
        try:
            last_g = discord.utils.parse_time(last_global)
        except Exception:
            last_g = None
        if last_g and (now - last_g) < timedelta(hours=PING_BANTER_GLOBAL_COOLDOWN_H):
            return False

    # Par utilisateur
    last_user = await _get_ping_ts(guild.id, str(target_user_id))
    if last_user:
        try:
            last_u = discord.utils.parse_time(last_user)
        except Exception:
            last_u = None
        if last_u and (now - last_u) < timedelta(days=PING_BANTER_USER_COOLDOWN_D):
            return False

    return True

async def record_ping_banter(guild: discord.Guild, target_user_id: int):
    await _set_ping_ts(guild.id, "GLOBAL")
    await _set_ping_ts(guild.id, str(target_user_id))

# ====== READY ======
@bot.event
async def on_ready():
    await ensure_schema()
    try:
        await bot.tree.sync()
    except Exception:
        pass
    print(f"✅ Connecté en tant que {bot.user} — slash cmds sync OK")

# ====== BIENVENUE ======
@bot.event
async def on_member_join(member: discord.Member):
    try:
        await bump_seen(member.guild.id, member.id, provoked=False)
        ch = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if not ch or not isinstance(ch, discord.TextChannel):
            return
        base = random.choice(WELCOME_LINES)(member.mention)
        extra = ""
        if should_drop_ticket_hint():
            tl = ticket_line()
            if tl:
                extra = "\\n\\n" + tl

        embed = discord.Embed(description=f"{base}{extra}", color=0x9B6B43)
        embed.set_author(name="Miri — Accueil")
        embed.set_footer(text="Bienvenue et amuse-toi bien !")
        await ch.send(content=member.mention, embed=embed)
    except Exception as e:
        print("Erreur on_member_join:", e)

# ====== MESSAGES ======
@bot.event
async def on_message(message: discord.Message):
    try:
        if message.author.bot or not message.guild:
            return

        await bump_seen(message.guild.id, message.author.id, provoked=False)

        # 1) Mention de Miri -> réponse IA (angry si provocation)
        if bot.user and bot.user in message.mentions:
            if hit_cd(mention_cd, message.author.id, COOLDOWN_SECONDS):
                content = message.clean_content
                provok = any(t in content.lower() for t in [
                    "ferme-la", "fdp", "ta gueule", "tg", "pute", "nul", "clash", "trash toi", "bouffonne"
                ])
                if provok:
                    await bump_seen(message.guild.id, message.author.id, provoked=True)
                tone = "angry" if provok else "normal"
                reply = await ai_reply(content, message.guild, message.author, tone=tone)
                await message.reply(reply)
            return

        # 2) Réponse lorsqu’on répond à un message de Miri
        if message.reference and message.reference.message_id:
            try:
                ref = await message.channel.fetch_message(message.reference.message_id)
                if ref.author.id == bot.user.id and hit_cd(reply_cd, message.author.id, COOLDOWN_SECONDS):
                    reply = await ai_reply(message.content, message.guild, message.author, tone="normal")
                    await message.reply(reply)
                    return
            except Exception:
                pass

        # 3) Banter auto : sans ping par défaut; ping exceptionnel si calme + cooldowns OK
        if BANTER_ENABLED and hit_cd(banter_cd, message.author.id, BANTER_COOLDOWN_SECONDS):
            if random.random() < BANTER_PROBABILITY:
                will_ping = False
                if isinstance(message.channel, discord.TextChannel):
                    quiet = await channel_is_quiet(message.channel)
                else:
                    quiet = False

                if quiet and await can_ping_banter(message.guild, message.author.id):
                    will_ping = True

                banter_text = await ai_reply(message.content, message.guild, message.author, tone="banter")
                if will_ping:
                    await message.channel.send(f"{message.author.mention} {banter_text}")
                    await record_ping_banter(message.guild, message.author.id)
                else:
                    await message.channel.send(banter_text)

    except Exception as e:
        print("Erreur on_message:", e)

# ====== SLASH COMMANDS ======
# Whitelist management (ADMIN)
@app_commands.default_permissions(administrator=True)
class WLGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="wl", description="Gérer la whitelist des pings de Miri")

    @app_commands.command(name="user_add", description="Ajouter un utilisateur à la whitelist")
    async def user_add(self, interaction: discord.Interaction, user: discord.User):
        async with await db() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO whitelist_users (guild_id, user_id) VALUES (?, ?)",
                (str(interaction.guild_id), str(user.id))
            )
            await conn.commit()
        await interaction.response.send_message(f"✅ {user.mention} ajouté à la whitelist.", ephemeral=True)

    @app_commands.command(name="user_remove", description="Retirer un utilisateur de la whitelist")
    async def user_remove(self, interaction: discord.Interaction, user: discord.User):
        async with await db() as conn:
            await conn.execute(
                "DELETE FROM whitelist_users WHERE guild_id=? AND user_id=?",
                (str(interaction.guild_id), str(user.id))
            )
            await conn.commit()
        await interaction.response.send_message(f"🗑️ {user.mention} retiré de la whitelist.", ephemeral=True)

    @app_commands.command(name="role_add", description="Ajouter un rôle à la whitelist")
    async def role_add(self, interaction: discord.Interaction, role: discord.Role):
        async with await db() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO whitelist_roles (guild_id, role_id) VALUES (?, ?)",
                (str(interaction.guild_id), str(role.id))
            )
            await conn.commit()
        await interaction.response.send_message(f"✅ Rôle {role.mention} ajouté à la whitelist.", ephemeral=True)

    @app_commands.command(name="role_remove", description="Retirer un rôle de la whitelist")
    async def role_remove(self, interaction: discord.Interaction, role: discord.Role):
        async with await db() as conn:
            await conn.execute(
                "DELETE FROM whitelist_roles WHERE guild_id=? AND role_id=?",
                (str(interaction.guild_id), str(role.id))
            )
            await conn.commit()
        await interaction.response.send_message(f"🗑️ Rôle {role.mention} retiré de la whitelist.", ephemeral=True)

    @app_commands.command(name="list", description="Voir la whitelist")
    async def list_all(self, interaction: discord.Interaction):
        async with await db() as conn:
            cu = await conn.execute(
                "SELECT user_id FROM whitelist_users WHERE guild_id=?",
                (str(interaction.guild_id),)
            )
            cr = await conn.execute(
                "SELECT role_id FROM whitelist_roles WHERE guild_id=?",
                (str(interaction.guild_id),)
            )
            users = [f"<@{row[0]}>" for row in await cu.fetchall()]
            roles = [f"<@&{row[0]}>" for row in await cr.fetchall()]
        txt = "**Users:** " + (", ".join(users) if users else "—")
        txt += "\\n**Rôles:** " + (", ".join(roles) if roles else "—")
        await interaction.response.send_message(txt, ephemeral=True)

bot.tree.add_command(WLGroup())

# Mémoire manuelle (ADMIN)
@app_commands.default_permissions(administrator=True)
class MemoryGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="memory", description="Gérer la mémoire de Miri")

    @app_commands.command(name="add", description="Ajouter une note sur un membre (mémoire persistante)")
    async def add_cmd(self, interaction: discord.Interaction, member: discord.Member, note: str):
        await add_note(interaction.guild_id, member.id, note)
        await interaction.response.send_message(f"🧠 Note ajoutée pour {member.mention}.", ephemeral=True)

    @app_commands.command(name="show", description="Voir les dernières notes sur un membre")
    async def show_cmd(self, interaction: discord.Interaction, member: discord.Member):
        notes = await get_notes(interaction.guild_id, member.id, limit=10)
        if not notes:
            await interaction.response.send_message("Aucune note.", ephemeral=True)
            return
        txt = "\\n".join(f"• {n}" for n in notes)
        await interaction.response.send_message(f"**Notes pour {member.mention}:**\\n{txt}", ephemeral=True)

bot.tree.add_command(MemoryGroup())

# Fait parler Miri sans ping (tout le monde peut demander)
@app_commands.command(name="miri_say", description="Demander à Miri de dire quelque chose (sans ping)")
async def miri_say(interaction: discord.Interaction, texte: str):
    if not interaction.guild:
        return
    reply = await ai_reply(texte, interaction.guild, interaction.user, tone="normal")
    await interaction.response.send_message(reply)

# PING explicite (WL uniquement) — param: membre à ping + texte transformé par l’IA
@app_commands.command(name="miri_ping", description="(WL) Demander à Miri de ping quelqu’un avec un message généré par l’IA")
@app_commands.describe(member="Membre à ping", texte="Idée/contexte du message que l’IA doit transformer (ton banter)")
async def miri_ping(interaction: discord.Interaction, member: discord.Member, texte: str):
    if not interaction.guild:
        return

    if not await can_requester_authorize_ping(interaction):
        await interaction.response.send_message(
            "❌ Je n’obéis pas à tout le monde. Tu n’es pas dans ma whitelist.",
            ephemeral=True
        )
        return

    # Génère un message piquant mais safe
    reply = await ai_reply(texte, interaction.guild, member, tone="banter")
    await interaction.response.send_message(f"{member.mention} {reply}")

# ====== RUN ======
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
