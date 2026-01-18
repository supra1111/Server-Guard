# ======================================================
# ================ ULTRA GUARD BOT FINAL =================
# ====================== PREFIX ! ======================
# ================== RAILWAY EDITION ==================
# ==================== NO PANEL =======================
# ======================================================

import discord
from discord.ext import commands
import datetime, time, os, re
from collections import defaultdict, deque

# ===================== START ==========================
START_TIME = time.time()

# ===================== CONFIG =========================
TOKEN = os.getenv("TOKEN")
PREFIX = "!"
LOG_CHANNEL_NAME = "ultra-guard-log"
TIMEOUT_MIN = 15

# ===================== GUARD AYARLARI =================
GUARDS = {
    "everyone": True,
    "emoji": True,
    "link": True,
    "channel": True,
    "role": True,
    "webhook": True,
    "botraid": True
}

EVERYONE_LIMIT = 3
EVERYONE_WINDOW = 15
EMOJI_LIMIT = 6
EMOJI_WINDOW = 10
LINK_LIMIT = 3
LINK_WINDOW = 15
WEBHOOK_LIMIT = 3
WEBHOOK_WINDOW = 10

# ===================== WHITELIST ======================
WHITELIST_USERS = set()
WHITELIST_ROLES = {"Founder", "Owner", "Admin"}

# ===================== INTENTS ========================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.webhooks = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ===================== TRACKERS =======================
everyone_tracker = defaultdict(lambda: deque())
emoji_tracker = defaultdict(lambda: deque())
link_tracker = defaultdict(lambda: deque())
webhook_tracker = defaultdict(lambda: deque())
guard_logs = deque(maxlen=200)

# ===================== HELPERS ========================
def is_whitelisted(member: discord.Member):
    if not member:
        return False
    if member.guild.owner_id == member.id:
        return True
    if member.id in WHITELIST_USERS:
        return True
    return any(r.name in WHITELIST_ROLES for r in member.roles)

async def get_log_channel(guild):
    ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if not ch:
        ch = await guild.create_text_channel(LOG_CHANNEL_NAME)
    return ch

async def log_event(guild, title, desc):
    ch = await get_log_channel(guild)
    embed = discord.Embed(
        title=title,
        description=desc,
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    await ch.send(embed=embed)
    guard_logs.appendleft(f"[{title}] {desc}")

async def punish(member, reason):
    try:
        await member.timeout(
            datetime.timedelta(minutes=TIMEOUT_MIN),
            reason=reason
        )
    except:
        pass

def spike(tracker, uid, limit, window):
    now = time.time()
    dq = tracker[uid]
    while dq and now - dq[0] > window:
        dq.popleft()
    dq.append(now)
    return len(dq) >= limit

def emoji_count(text):
    return len(re.findall(r"[\U00010000-\U0010ffff]", text))

def has_link(text):
    return bool(re.search(r"https?://|discord\.gg|www\.", text.lower()))

# ===================== EVENTS =========================
@bot.event
async def on_ready():
    print(f"🛡️ ULTRA GUARD AKTİF: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    content = message.content

    # Everyone / Here
    if GUARDS["everyone"] and ("@everyone" in content or "@here" in content):
        if not is_whitelisted(message.author):
            if spike(everyone_tracker, uid, EVERYONE_LIMIT, EVERYONE_WINDOW):
                await punish(message.author, "Everyone/Here Spam")
                await log_event(message.guild, "📢 EVERYONE SPAM", message.author.mention)

    # Emoji spam
    if GUARDS["emoji"] and emoji_count(content) >= EMOJI_LIMIT:
        if not is_whitelisted(message.author):
            if spike(emoji_tracker, uid, EMOJI_LIMIT, EMOJI_WINDOW):
                await punish(message.author, "Emoji Spam")
                await log_event(message.guild, "😈 EMOJI SPAM", message.author.mention)

    # Link spam
    if GUARDS["link"] and has_link(content):
        if not is_whitelisted(message.author):
            if spike(link_tracker, uid, LINK_LIMIT, LINK_WINDOW):
                await punish(message.author, "Link Spam")
                await log_event(message.guild, "🔗 LINK SPAM", message.author.mention)

    await bot.process_commands(message)

# -------- CHANNEL DELETE --------
@bot.event
async def on_guild_channel_delete(channel):
    if not GUARDS["channel"]:
        return
    async for entry in channel.guild.audit_logs(
        limit=1,
        action=discord.AuditLogAction.channel_delete
    ):
        if is_whitelisted(entry.user) or entry.user == bot.user:
            return
        await punish(entry.user, "Channel Nuke")
        await log_event(channel.guild, "🗑️ CHANNEL NUKE", entry.user.mention)

# -------- ROLE DELETE --------
@bot.event
async def on_guild_role_delete(role):
    if not GUARDS["role"]:
        return
    async for entry in role.guild.audit_logs(
        limit=1,
        action=discord.AuditLogAction.role_delete
    ):
        if is_whitelisted(entry.user) or entry.user == bot.user:
            return
        await punish(entry.user, "Role Nuke")
        await log_event(role.guild, "🧨 ROLE NUKE", entry.user.mention)

# -------- WEBHOOK NUKE --------
@bot.event
async def on_webhooks_update(channel):
    if not GUARDS["webhook"]:
        return
    async for entry in channel.guild.audit_logs(
        limit=1,
        action=discord.AuditLogAction.webhook_create
    ):
        if is_whitelisted(entry.user) or entry.user == bot.user:
            return
        if spike(webhook_tracker, entry.user.id, WEBHOOK_LIMIT, WEBHOOK_WINDOW):
            try:
                for wh in await channel.webhooks():
                    await wh.delete(reason="Webhook Nuke")
            except:
                pass
            await punish(entry.user, "Webhook Nuke")
            await log_event(channel.guild, "🔗 WEBHOOK NUKE", entry.user.mention)

# -------- BOT RAID --------
@bot.event
async def on_member_join(member):
    if not GUARDS["botraid"] or not member.bot:
        return
    async for entry in member.guild.audit_logs(
        limit=1,
        action=discord.AuditLogAction.bot_add
    ):
        if is_whitelisted(entry.user):
            return
        await member.kick(reason="Bot Raid")
        await punish(entry.user, "Bot Raid")
        await log_event(member.guild, "🤖 BOT RAID", entry.user.mention)

# ===================== COMMANDS (20+) ==================
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong")

@bot.command()
async def uptime(ctx):
    await ctx.send(f"⏱️ {int(time.time()-START_TIME)} saniyedir aktif")

@bot.command()
async def guards(ctx):
    text = "\n".join(f"{k}: {'ON' if v else 'OFF'}" for k, v in GUARDS.items())
    await ctx.send(f"```{text}```")

@bot.command()
async def guardlog(ctx):
    text = "\n".join(list(guard_logs)[:10]) or "Log yok"
    await ctx.send(f"```{text}```")

@bot.command()
async def say(ctx, *, msg):
    await ctx.send(msg)

@bot.command()
async def clear(ctx, amount: int = 10):
    await ctx.channel.purge(limit=amount + 1)

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    await ctx.send(f"🏠 {g.name}\n👥 {g.member_count} üye")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    m = member or ctx.author
    await ctx.send(f"👤 {m}\n🆔 {m.id}")

@bot.command()
async def whitelist(ctx):
    users = ", ".join(str(u) for u in WHITELIST_USERS) or "Yok"
    roles = ", ".join(WHITELIST_ROLES)
    await ctx.send(f"Users: {users}\nRoles: {roles}")

@bot.command()
async def addwl(ctx, user: discord.Member):
    if ctx.author.guild_permissions.administrator:
        WHITELIST_USERS.add(user.id)
        await ctx.send("✅ Whitelist eklendi")

@bot.command()
async def removewl(ctx, user: discord.Member):
    if ctx.author.guild_permissions.administrator:
        WHITELIST_USERS.discard(user.id)
        await ctx.send("❌ Whitelist kaldırıldı")

@bot.command()
async def helpguard(ctx):
    await ctx.send("🛡️ Ultra Guard aktif. Prefix: !")

# ===================== RUN =============================
bot.run(TOKEN)
