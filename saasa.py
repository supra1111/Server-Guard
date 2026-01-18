# ======================================================
# ================ ULTRA GUARD BOT v4.6 =================
# ====================== PREFIX ! ======================
# ================== RAILWAY EDITION ==================
# ======================================================

import discord
from discord.ext import commands
import datetime, time, os, re
from collections import defaultdict, deque
from flask import Flask, request, redirect
from threading import Thread

# ================= PANEL + KEEP ALIVE =================
app = Flask("UltraGuardPanel")
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "changeme")
panel_sessions = set()

WHITELIST_USERS = set()
WHITELIST_ROLES = {"Founder", "Owner", "Admin"}
guard_logs = deque(maxlen=100)

# GUARD DURUMLARI (PANELDEN KONTROL)
GUARDS = {
    "everyone": True,
    "emoji": True,
    "link": True,
    "channel": True,
    "role": True,
    "webhook": True,
    "botraid": True
}

@app.route("/", methods=["GET", "POST"])
def panel():
    ip = request.remote_addr

    # LOGIN
    if ip not in panel_sessions:
        if request.method == "POST":
            if request.form.get("password") == PANEL_PASSWORD:
                panel_sessions.add(ip)
                return redirect("/")
            return "<h3>❌ Yanlış şifre</h3>"
        return """
        <h2>🔐 Ultra Guard Panel</h2>
        <form method="post">
        <input type="password" name="password" placeholder="Panel Şifresi">
        <button type="submit">Giriş</button>
        </form>
        """

    # POST ACTIONS
    if request.method == "POST":

        # WHITELIST USERS
        if "add_user" in request.form:
            try:
                WHITELIST_USERS.add(int(request.form["user_id"]))
            except:
                pass
        if "remove_user" in request.form:
            try:
                WHITELIST_USERS.discard(int(request.form["user_id"]))
            except:
                pass

        # WHITELIST ROLES
        if "add_role" in request.form:
            WHITELIST_ROLES.add(request.form["role_name"])
        if "remove_role" in request.form:
            WHITELIST_ROLES.discard(request.form["role_name"])

        # GUARD TOGGLES
        for g in GUARDS:
            GUARDS[g] = g in request.form

    users_html = "<br>".join(str(u) for u in WHITELIST_USERS) or "Yok"
    roles_html = "<br>".join(WHITELIST_ROLES)
    logs_html = "<br>".join(list(guard_logs)[:30]) or "Log yok"

    guard_html = "".join([
        f'<input type="checkbox" name="{g}" {"checked" if GUARDS[g] else ""}> {g.upper()}<br>'
        for g in GUARDS
    ])

    return f"""
    <h1>🛡️ Ultra Guard Panel</h1>

    <h2>⚙️ Guard Aç / Kapat</h2>
    <form method="post">
        {guard_html}
        <button type="submit">Kaydet</button>
    </form>

    <hr>

    <h2>👤 Whitelist Users</h2>
    {users_html}
    <form method="post">
        <input name="user_id" placeholder="User ID">
        <button name="add_user">Ekle</button>
        <button name="remove_user">Sil</button>
    </form>

    <h2>🎭 Whitelist Roles</h2>
    {roles_html}
    <form method="post">
        <input name="role_name" placeholder="Role Name">
        <button name="add_role">Ekle</button>
        <button name="remove_role">Sil</button>
    </form>

    <h2>📜 Son Loglar</h2>
    {logs_html}
    """

def run():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

Thread(target=run).start()

# ================= DISCORD CONFIG =====================
TOKEN = os.getenv("TOKEN")
PREFIX = "!"
LOG_CHANNEL_NAME = "ultra-guard-log"
TIMEOUT_MIN = 15

EVERYONE_LIMIT = 3
EVERYONE_WINDOW = 15
EMOJI_LIMIT = 6
EMOJI_WINDOW = 10
LINK_LIMIT = 3
LINK_WINDOW = 15
WEBHOOK_LIMIT = 3
WEBHOOK_WINDOW = 10

# ================= INTENTS ============================
intents = discord.Intents.none()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.moderation = True
intents.webhooks = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ================= TRACKERS ===========================
everyone_tracker = defaultdict(lambda: deque())
emoji_tracker = defaultdict(lambda: deque())
link_tracker = defaultdict(lambda: deque())
webhook_tracker = defaultdict(lambda: deque())

# ================= HELPERS ============================
def is_whitelisted(member):
    if not member:
        return False
    if member.guild.owner_id == member.id:
        return True
    if member.id in WHITELIST_USERS:
        return True
    return any(r.name in WHITELIST_ROLES for r in member.roles)

async def log_event(guild, title, desc):
    ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if not ch:
        ch = await guild.create_text_channel(LOG_CHANNEL_NAME)
    embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
    await ch.send(embed=embed)
    guard_logs.appendleft(f"[{title}] {desc}")

async def punish(member, reason):
    try:
        await member.timeout(datetime.timedelta(minutes=TIMEOUT_MIN), reason=reason)
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

# ================= EVENTS =============================
@bot.event
async def on_ready():
    print(f"🛡️ ULTRA GUARD v4.6 AKTİF: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    content = message.content

    if GUARDS["everyone"] and ("@everyone" in content or "@here" in content) and not is_whitelisted(message.author):
        if spike(everyone_tracker, uid, EVERYONE_LIMIT, EVERYONE_WINDOW):
            await punish(message.author, "Everyone Spam")
            await log_event(message.guild, "📢 EVERYONE SPAM", message.author.mention)

    if GUARDS["emoji"] and emoji_count(content) >= EMOJI_LIMIT and not is_whitelisted(message.author):
        if spike(emoji_tracker, uid, EMOJI_LIMIT, EMOJI_WINDOW):
            await punish(message.author, "Emoji Spam")
            await log_event(message.guild, "😈 EMOJI SPAM", message.author.mention)

    if GUARDS["link"] and has_link(content) and not is_whitelisted(message.author):
        if spike(link_tracker, uid, LINK_LIMIT, LINK_WINDOW):
            await punish(message.author, "Link Spam")
            await log_event(message.guild, "🔗 LINK SPAM", message.author.mention)

    await bot.process_commands(message)

@bot.event
async def on_guild_channel_delete(channel):
    if not GUARDS["channel"]:
        return
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        if is_whitelisted(entry.user) or entry.user == bot.user:
            return
        await punish(entry.user, "Channel Nuke")
        await log_event(channel.guild, "🗑️ CHANNEL NUKE", entry.user.mention)

@bot.event
async def on_guild_role_delete(role):
    if not GUARDS["role"]:
        return
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        if is_whitelisted(entry.user) or entry.user == bot.user:
            return
        await punish(entry.user, "Role Nuke")
        await log_event(role.guild, "🧨 ROLE NUKE", entry.user.mention)

@bot.event
async def on_webhooks_update(channel):
    if not GUARDS["webhook"]:
        return
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.webhook_create):
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

@bot.event
async def on_member_join(member):
    if not GUARDS["botraid"] or not member.bot:
        return
    async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
        if is_whitelisted(entry.user):
            return
        await member.kick(reason="Bot Raid")
        await punish(entry.user, "Bot Raid")
        await log_event(member.guild, "🤖 BOT RAID", entry.user.mention)

# ================= COMMANDS ===========================
@bot.command()
async def guardlog(ctx):
    if not is_whitelisted(ctx.author):
        return
    text = "\n".join(list(guard_logs)[:10]) or "Log yok"
    await ctx.send(f"```{text}```")

@bot.command()
async def whitelist(ctx):
    if not is_whitelisted(ctx.author):
        return
    users = ", ".join([f"<@{u}>" for u in WHITELIST_USERS]) or "Yok"
    roles = ", ".join(WHITELIST_ROLES)
    await ctx.send(f"👤 Users: {users}\n🎭 Roles: {roles}")

# ================= RUN ================================
bot.run(TOKEN)
