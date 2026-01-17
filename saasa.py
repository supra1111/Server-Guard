# ======================================================
# ================ ULTRA GUARD BOT ===================
# ====================== ! PREFIX =====================
# ======================================================

import discord
from discord.ext import commands, tasks
import datetime, time, asyncio
from collections import defaultdict, deque
from copy import deepcopy
import matplotlib.pyplot as plt
import io

# ================= CONFIG ============================
TOKEN = "TOKEN_BOT_HERE"  # <--- Tokeni buraya koy
PREFIX = "!"
LOG_CHANNEL = "guard-log"
TIMEOUT_MIN = 15

ANTI_NUKE_LIMIT = 3
ANTI_NUKE_WINDOW = 10
SPIKE_LIMIT = 5
SPIKE_WINDOW = 12
BOT_JOIN_LIMIT = 3
BOT_JOIN_WINDOW = 30

DM_ALARM = True
AUTO_LOCKDOWN = True

WHITELIST_USERS = []
WHITELIST_ROLES = ["Founder", "Owner", "Admin"]

# ================= INTENTS ===========================
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ================= TRACKERS ==========================
nuke_tracker = defaultdict(lambda: deque())
spike_tracker = defaultdict(lambda: deque())
bot_join_tracker = deque()
role_backup = {}
channel_backup = {}
stats = defaultdict(int)
attack_profile = defaultdict(lambda: defaultdict(int))

# ================= SPAM TRACKER ======================
MESSAGE_LIMIT = 5
MESSAGE_WINDOW = 15
spam_tracker = defaultdict(lambda: deque())

# ================= HELPERS ==========================
def whitelist_mi(member: discord.Member):
    if not member:
        return False
    if member.guild.owner_id == member.id:
        return True
    if member.id in WHITELIST_USERS:
        return True
    for r in member.roles:
        if r.name in WHITELIST_ROLES:
            return True
    return False

async def get_log_channel(guild):
    ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL)
    if not ch:
        ch = await guild.create_text_channel(LOG_CHANNEL)
    return ch

async def log(guild, title, desc):
    ch = await get_log_channel(guild)
    embed = discord.Embed(
        title=title,
        description=desc,
        color=discord.Color.dark_red(),
        timestamp=datetime.datetime.utcnow()
    )
    await ch.send(embed=embed)

async def ceza(member, sebep):
    try:
        await member.timeout(datetime.timedelta(minutes=TIMEOUT_MIN), reason=sebep)
    except:
        pass

def anti_nuke(uid):
    now = time.time()
    dq = nuke_tracker[uid]
    while dq and now - dq[0] > ANTI_NUKE_WINDOW:
        dq.popleft()
    dq.append(now)
    return len(dq) >= ANTI_NUKE_LIMIT

def spike(event):
    now = time.time()
    dq = spike_tracker[event]
    while dq and now - dq[0] > SPIKE_WINDOW:
        dq.popleft()
    dq.append(now)
    return len(dq) >= SPIKE_LIMIT

async def backup_guild(guild):
    role_backup[guild.id] = {r.id: deepcopy(r.permissions) for r in guild.roles}
    channel_backup[guild.id] = {ch.id: ch.overwrites for ch in guild.channels}

async def lockdown(guild, sebep):
    await backup_guild(guild)
    for ch in guild.channels:
        try:
            await ch.set_permissions(guild.default_role, send_messages=False, connect=False)
        except:
            pass
    await log(guild, "☢️ GOD MODE LOCKDOWN", sebep)
    await dm_alarm(guild, sebep)

async def restore_lockdown(guild):
    if guild.id not in channel_backup:
        return False
    for ch in guild.channels:
        if ch.id in channel_backup[guild.id]:
            try:
                await ch.edit(overwrites=channel_backup[guild.id][ch.id])
            except:
                pass
    for r in guild.roles:
        if r.id in role_backup.get(guild.id, {}):
            try:
                await r.edit(permissions=role_backup[guild.id][r.id])
            except:
                pass
    await log(guild, "🔓 LOCKDOWN KALDIRILDI", "Sunucu eski haline döndü")
    return True

async def dm_alarm(guild, sebep):
    if not DM_ALARM:
        return
    targets = set()
    if guild.owner:
        targets.add(guild.owner)
    for r in guild.roles:
        if r.name in WHITELIST_ROLES:
            for m in r.members:
                targets.add(m)
    embed = discord.Embed(
        title="🚨 GOD MODE GUARD ALARM",
        description="Sunucu SALDIRI ALTINDA!",
        color=discord.Color.red()
    )
    embed.add_field(name="Sebep", value=sebep, inline=False)
    for u in targets:
        try:
            await u.send(embed=embed)
        except:
            pass

# ================= EVENTS ============================
@bot.event
async def on_ready():
    print(f"🔥 ULTRA GUARD BOT AKTİF: {bot.user}")

# Spam ve !komutları yakalamak için on_message
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    # Spam tracker
    now = time.time()
    dq = spam_tracker[message.author.id]
    while dq and now - dq[0][1] > MESSAGE_WINDOW:
        dq.popleft()
    dq.append((message.content, now))
    same_messages = [m for m, _ in dq if m == message.content]
    if len(same_messages) >= MESSAGE_LIMIT and not whitelist_mi(message.author):
        try:
            await message.author.timeout(
                datetime.timedelta(minutes=TIMEOUT_MIN),
                reason=f"Spam: Aynı mesajı {MESSAGE_LIMIT} kez gönderdi"
            )
        except:
            pass
        await log(message.guild, "🚫 SPAM GUARD",
                  f"{message.author.mention} aynı mesajı **{MESSAGE_LIMIT} kez** attı ve timeout aldı.")
        dq.clear()

    # Komutların çalışması için
    await bot.process_commands(message)

# Ban, kanal ve bot join guard
@bot.event
async def on_member_ban(guild, user):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        if whitelist_mi(entry.user):
            return
        await guild.unban(user)
        await ceza(entry.user, "Ban Nuke")
        stats["ban"] += 1
        attack_profile[entry.user.id]["ban"] += 1
        await log(guild, "🛑 BAN GUARD", entry.user.mention)
        if anti_nuke(entry.user.id) or spike("ban"):
            await lockdown(guild, "Ban Nuke Algılandı")

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(limit=1):
        if whitelist_mi(entry.user):
            return
        await ceza(entry.user, "Channel Nuke")
        stats["channel"] += 1
        attack_profile[entry.user.id]["channel"] += 1
        await log(channel.guild, "🛑 CHANNEL GUARD", entry.user.mention)
        if anti_nuke(entry.user.id) or spike("channel"):
            await lockdown(channel.guild, "Kanal Nuke")

@bot.event
async def on_member_join(member):
    if member.bot:
        now = time.time()
        bot_join_tracker.append(now)
        while bot_join_tracker and now - bot_join_tracker[0] > BOT_JOIN_WINDOW:
            bot_join_tracker.popleft()
        async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
            if whitelist_mi(entry.user):
                return
            await member.kick(reason="Bot Raid")
            await ceza(entry.user, "Bot Raid")
            await log(member.guild, "🤖 BOT RAID", entry.user.mention)
            if len(bot_join_tracker) >= BOT_JOIN_LIMIT:
                await lockdown(member.guild, "Bot Raid Tespiti")

# ================== ! KOMUT PANELİ =====================
@bot.command(name="lockdown")
async def cmd_lockdown(ctx):
    if not whitelist_mi(ctx.author):
        return await ctx.send("❌ Yetki yok")
    await lockdown(ctx.guild, f"Manuel Lockdown: {ctx.author}")
    await ctx.send("☢️ Lockdown aktif!")

@bot.command(name="unlock")
async def cmd_unlock(ctx):
    if not whitelist_mi(ctx.author):
        return await ctx.send("❌ Yetki yok")
    if await restore_lockdown(ctx.guild):
        await ctx.send("🔓 Lockdown kaldırıldı")
    else:
        await ctx.send("⚠️ Aktif lockdown yok")

@bot.command(name="rapor")
async def cmd_rapor(ctx):
    # Grafik oluştur
    events = ["ban", "channel"]
    counts = [stats[e] for e in events]
    plt.bar(events, counts, color=["red", "blue"])
    plt.title("Guard Bot Saldırı Raporu")
    plt.ylabel("Olay Sayısı")
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    file = discord.File(buf, filename="rapor.png")
    embed = discord.Embed(
        title="📊 Saldırı Raporu",
        description="Sunucudaki guard istatistikleri",
        color=discord.Color.dark_blue(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_image(url="attachment://rapor.png")
    await ctx.send(embed=embed, file=file)

# ================= RUN ================================
bot.run(TOKEN)
