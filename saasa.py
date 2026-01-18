# ======================================================
# ================ ULTRA GUARD BOT v6 ==================
# ====================== PREFIX ! ======================
# ================== RAILWAY EDITION ==================
# ======================================================

import discord
from discord.ext import commands
import datetime, time, os, re, asyncio
from collections import defaultdict, deque

# ================= BASIC CONFIG =======================
TOKEN = os.getenv("TOKEN")
PREFIX = "!"
LOG_CHANNEL_NAME = "ultra-guard-log"
TIMEOUT_MIN = 15
START_TIME = time.time()

# ================= GUARD STATES =======================
GUARDS = {
    "everyone": True,
    "emoji": True,
    "link": True,
    "channel": True,
    "role": True,
    "webhook": True,
    "botraid": True,
    "nick": True,
    "massban": True,
    "masskick": True,
    "rolegive": True
}

# ================= LIMITS =============================
LIMITS = {
    "everyone": (3, 15),
    "emoji": (6, 10),
    "link": (3, 15),
    "nick": (3, 20),
    "ban": (2, 30),
    "kick": (3, 30),
    "role": (3, 20),
    "webhook": (3, 10)
}

# ================= DATA ===============================
WHITELIST_USERS = set()
WHITELIST_ROLES = {"Founder", "Owner", "Admin"}
guard_logs = deque(maxlen=200)

trackers = defaultdict(lambda: defaultdict(lambda: deque()))

# ================= INTENTS ============================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ================= HELPERS ============================
def is_whitelisted(member):
    if not member:
        return False
    if member.guild.owner_id == member.id:
        return True
    if member.id in WHITELIST_USERS:
        return True
    return any(r.name in WHITELIST_ROLES for r in member.roles)

def spike(key, uid):
    limit, window = LIMITS[key]
    dq = trackers[key][uid]
    now = time.time()
    while dq and now - dq[0] > window:
        dq.popleft()
    dq.append(now)
    return len(dq) >= limit

def emoji_count(text):
    return len(re.findall(r"[\U00010000-\U0010ffff]", text))

def has_link(text):
    return bool(re.search(r"https?://|discord\.gg|www\.", text.lower()))

async def punish(member, reason):
    try:
        await member.timeout(datetime.timedelta(minutes=TIMEOUT_MIN), reason=reason)
    except:
        pass

async def log_event(guild, title, desc):
    ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if not ch:
        ch = await guild.create_text_channel(LOG_CHANNEL_NAME)
    embed = discord.Embed(
        title=title,
        description=desc,
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    await ch.send(embed=embed)
    guard_logs.appendleft(f"[{title}] {desc}")

# ================= EVENTS =============================
@bot.event
async def on_ready():
    print(f"🛡️ ULTRA GUARD v6 AKTİF: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    content = message.content

    if GUARDS["everyone"] and ("@everyone" in content or "@here" in content) and not is_whitelisted(message.author):
        if spike("everyone", uid):
            await punish(message.author, "Everyone Spam")
            await log_event(message.guild, "EVERYONE SPAM", message.author.mention)

    if GUARDS["emoji"] and emoji_count(content) >= LIMITS["emoji"][0] and not is_whitelisted(message.author):
        if spike("emoji", uid):
            await punish(message.author, "Emoji Spam")
            await log_event(message.guild, "EMOJI SPAM", message.author.mention)

    if GUARDS["link"] and has_link(content) and not is_whitelisted(message.author):
        if spike("link", uid):
            await punish(message.author, "Link Spam")
            await log_event(message.guild, "LINK SPAM", message.author.mention)

    await bot.process_commands(message)

@bot.event
async def on_member_update(before, after):
    if GUARDS["nick"] and before.nick != after.nick and not is_whitelisted(after):
        if spike("nick", after.id):
            await punish(after, "Nickname Spam")
            await log_event(after.guild, "NICK SPAM", after.mention)

@bot.event
async def on_member_ban(guild, user):
    if GUARDS["massban"]:
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
            if not is_whitelisted(entry.user) and spike("ban", entry.user.id):
                await punish(entry.user, "Mass Ban")
                await log_event(guild, "MASS BAN", entry.user.mention)

@bot.event
async def on_member_remove(member):
    if GUARDS["masskick"]:
        async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
            if not is_whitelisted(entry.user) and spike("kick", entry.user.id):
                await punish(entry.user, "Mass Kick")
                await log_event(member.guild, "MASS KICK", entry.user.mention)

@bot.event
async def on_guild_role_update(before, after):
    if GUARDS["rolegive"] and len(after.members) > len(before.members):
        async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
            if not is_whitelisted(entry.user) and spike("role", entry.user.id):
                await punish(entry.user, "Role Abuse")
                await log_event(after.guild, "ROLE ABUSE", entry.user.mention)

@bot.event
async def on_guild_channel_delete(channel):
    if GUARDS["channel"]:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
            if not is_whitelisted(entry.user):
                await punish(entry.user, "Channel Nuke")
                await log_event(channel.guild, "CHANNEL NUKE", entry.user.mention)

@bot.event
async def on_guild_role_delete(role):
    if GUARDS["role"]:
        async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            if not is_whitelisted(entry.user):
                await punish(entry.user, "Role Nuke")
                await log_event(role.guild, "ROLE NUKE", entry.user.mention)

@bot.event
async def on_webhooks_update(channel):
    if GUARDS["webhook"]:
        async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
            if not is_whitelisted(entry.user) and spike("webhook", entry.user.id):
                await punish(entry.user, "Webhook Nuke")
                await log_event(channel.guild, "WEBHOOK NUKE", entry.user.mention)

@bot.event
async def on_member_join(member):
    if GUARDS["botraid"] and member.bot:
        async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            if not is_whitelisted(entry.user):
                await member.kick(reason="Bot Raid")
                await punish(entry.user, "Bot Raid")
                await log_event(member.guild, "BOT RAID", entry.user.mention)

# ================= COMMANDS (25+) =====================
@bot.command() async def ping(ctx): await ctx.send("🏓 Pong")
@bot.command() async def uptime(ctx): await ctx.send(f"⏱️ {int(time.time()-START_TIME)}s")
@bot.command() async def say(ctx, *, msg): await ctx.send(msg)
@bot.command() async def clear(ctx, a: int = 20): await ctx.channel.purge(limit=a+1)
@bot.command() async def lock(ctx): 
    for c in ctx.guild.text_channels: await c.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send("🔒 Kilitlendi")
@bot.command() async def unlock(ctx):
    for c in ctx.guild.text_channels: await c.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send("🔓 Açıldı")
@bot.command() async def slow(ctx, s: int): await ctx.channel.edit(slowmode_delay=s)
@bot.command() async def serverinfo(ctx): await ctx.send(f"👑 Owner: {ctx.guild.owner}")
@bot.command() async def userinfo(ctx, m: discord.Member=None):
    m=m or ctx.author; await ctx.send(f"{m} | ID: {m.id}")
@bot.command() async def guards(ctx):
    await ctx.send("```" + "\n".join(f"{k}:{'ON' if v else 'OFF'}" for k,v in GUARDS.items()) + "```")
@bot.command() async def guard(ctx,n=None,s=None):
    if n in GUARDS and s in ["on","off"]:
        GUARDS[n]=s=="on"; await ctx.send(f"{n} {s}")
@bot.command() async def wl(ctx,a=None,m:discord.Member=None):
    if a=="add": WHITELIST_USERS.add(m.id)
    if a=="remove": WHITELIST_USERS.discard(m.id)
@bot.command() async def whitelist(ctx):
    await ctx.send(", ".join(str(i) for i in WHITELIST_USERS))
@bot.command() async def guardlog(ctx):
    await ctx.send("```"+"\n".join(list(guard_logs)[:10])+"```")
@bot.command() async def kick(ctx,m:discord.Member): await m.kick()
@bot.command() async def ban(ctx,m:discord.Member): await m.ban()
@bot.command() async def unban(ctx,id:int):
    u=await bot.fetch_user(id); await ctx.guild.unban(u)
@bot.command() async def roleadd(ctx,m:discord.Member,r:discord.Role): await m.add_roles(r)
@bot.command() async def roleremove(ctx,m:discord.Member,r:discord.Role): await m.remove_roles(r)
@bot.command() async def nick(ctx,m:discord.Member,*,n): await m.edit(nick=n)
@bot.command() async def avatar(ctx,m:discord.Member=None):
    m=m or ctx.author; await ctx.send(m.avatar.url)

# ================= RUN ================================
bot.run(TOKEN)
