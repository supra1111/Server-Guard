import os
import discord
from discord.ext import commands, tasks
import datetime
from collections import defaultdict
import time
import matplotlib.pyplot as plt

# ================= AYARLAR =================
TOKEN = os.getenv("MTQ2MjA5MTc0NDIyMDAyMDk4MQ.GhWopT.pqao8T1Yb_5qF6Qlm5sAGT_v73fpYLFmmGox-A")
if not TOKEN or TOKEN == "TOKEN_BURAYA":
    raise ValueError("❌ Bot tokeni geçersiz veya boş. Lütfen .env dosyasına ekleyin veya TOKEN değişkenini güncelleyin.")

GUILD_ID = 1259126653838299209
YETKILI_ROL = "Channel Manager"
LOG_KANAL = "mod-log"
TIMEOUT_DK = 1
ANTI_NUKE_LIMIT = 5
ANTI_NUKE_TIME = 60
SPIKE_TIME_WINDOW = 60
SPIKE_THRESHOLD = 5
ALARM_DM = True

# ================= WHITELIST =================
WHITELIST_USERS = [123456789012345678]
WHITELIST_ROLES = ["Founder", "Admin"]

# ================= İSTATİSTİK =================
stats = {"spam":0,"kanal":0,"rol":0,"ban":0,"bot":0,"yetki":0,"webhook":0}
daily_stats = defaultdict(int)
weekly_stats = defaultdict(int)
hourly_stats = defaultdict(int)
nuke_log = defaultdict(list)
ceza_puani = defaultdict(int)
spike_events = defaultdict(list)
role_backup = {}

# ================= INTENTS =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= YARDIMCI FONKSİYONLAR =================
def whitelist_mi(member):
    if member.guild.owner_id == member.id: return True
    if member.id in WHITELIST_USERS: return True
    for rol in member.roles:
        if rol.name in WHITELIST_ROLES: return True
    return False

async def log(guild, title, desc):
    kanal = discord.utils.get(guild.text_channels, name=LOG_KANAL)
    if not kanal:
        kanal = await guild.create_text_channel(LOG_KANAL)
    embed = discord.Embed(title=title, description=desc, color=discord.Color.red(), timestamp=datetime.datetime.utcnow())
    await kanal.send(embed=embed)

async def ceza(member, sebep):
    try:
        await member.timeout(datetime.timedelta(minutes=TIMEOUT_DK), reason=sebep)
    except:
        pass

def kaydet(event):
    gun = datetime.date.today().isoformat()
    hafta = datetime.date.today().strftime("%Y-%W")
    daily_stats[f"{gun}-{event}"] += 1
    weekly_stats[f"{hafta}-{event}"] += 1

def saatlik_kaydet(event):
    saat = datetime.datetime.now().strftime("%Y-%m-%d %H")
    hourly_stats[f"{saat}-{event}"] += 1

def anti_nuke_check(user_id):
    now = time.time()
    nuke_log[user_id] = [t for t in nuke_log[user_id] if now - t < ANTI_NUKE_TIME]
    nuke_log[user_id].append(now)
    return len(nuke_log[user_id]) >= ANTI_NUKE_LIMIT

def spike_kontrol(event, user_id):
    now = time.time()
    spike_events[event] = [t for t in spike_events[event] if now - t < SPIKE_TIME_WINDOW]
    spike_events[event].append(now)
    return len(spike_events[event]) >= SPIKE_THRESHOLD

async def cezalandir(member, sebep):
    ceza_puani[member.id] += 1
    puan = ceza_puani[member.id]
    if puan == 1:
        await member.timeout(datetime.timedelta(minutes=1), reason=sebep)
    elif puan == 2:
        await member.kick(reason=sebep)
    else:
        await member.ban(reason=sebep)

# ================= YEDEKLEME & SAVUNMA =================
async def yedek_al(guild):
    role_backup[guild.id] = {}
    for role in guild.roles:
        role_backup[guild.id][role.id] = role.permissions

async def savunma_modu(guild, sebep):
    await yedek_al(guild)
    for role in guild.roles:
        if role.permissions.administrator or role.permissions.manage_roles or role.permissions.manage_channels:
            perms = role.permissions
            perms.update(administrator=False, manage_roles=False, manage_channels=False)
            try:
                await role.edit(permissions=perms)
            except:
                pass
    await log(guild, "☢️ SAVUNMA MODU AÇILDI", f"Sebep: {sebep}")
    await savunma_alarm_dm(guild, sebep)

async def savunma_kapat(guild):
    if guild.id not in role_backup:
        return False
    for role in guild.roles:
        if role.id in role_backup[guild.id]:
            try:
                await role.edit(permissions=role_backup[guild.id][role.id])
            except:
                pass
    await log(guild, "🔓 SAVUNMA MODU KAPATILDI", "Yetkiler geri yüklendi")
    return True

async def alarm_listesi(guild):
    alicilar = set()
    if guild.owner:
        alicilar.add(guild.owner)
    for uid in WHITELIST_USERS:
        member = guild.get_member(uid)
        if member: alicilar.add(member)
    for role in guild.roles:
        if role.name in WHITELIST_ROLES:
            for member in role.members:
                alicilar.add(member)
    return alicilar

async def savunma_alarm_dm(guild, sebep):
    if not ALARM_DM:
        return
    alicilar = await alarm_listesi(guild)
    embed = discord.Embed(
        title="☢️ SAVUNMA MODU AKTİF",
        description="Sunucu otomatik olarak korumaya alındı!",
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="Sunucu", value=guild.name, inline=False)
    embed.add_field(name="Sebep", value=sebep, inline=False)
    embed.add_field(name="Durum", value="Yetkiler geçici olarak kısıtlandı", inline=False)
    for uye in alicilar:
        try:
            await uye.send(embed=embed)
        except:
            pass

# ================= GRAFİK =================
def grafik_olustur(mod="genel"):
    if mod == "gunluk":
        data = daily_stats
        baslik = "📅 Günlük Guard İstatistikleri"
    elif mod == "haftalik":
        data = weekly_stats
        baslik = "🗓️ Haftalık Guard İstatistikleri"
    elif mod == "saatlik":
        data = hourly_stats
        baslik = "⏰ Saatlik Guard İstatistikleri"
    else:
        data = stats
        baslik = "📊 Genel Guard İstatistikleri"
    keys = list(data.keys())[-24:]
    values = list(data.values())[-24:]
    plt.figure(figsize=(10,4))
    plt.plot(keys, values, marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.title(baslik)
    plt.tight_layout()
    dosya = f"guard_{mod}.png"
    plt.savefig(dosya)
    plt.close()
    return dosya

# ================= PANEL VE UI =================
class SavunmaPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    @discord.ui.button(label="🔓 Savunmayı Kapat", style=discord.ButtonStyle.success)
    async def kapat(self, interaction, button):
        if not whitelist_mi(interaction.user):
            return await interaction.response.send_message("❌ Yetkin yok", ephemeral=True)
        basarili = await savunma_kapat(interaction.guild)
        if basarili:
            await interaction.response.send_message("✅ Savunma modu kapatıldı", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Aktif savunma modu yok", ephemeral=True)

class WhitelistPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
    @discord.ui.button(label="➕ Ekle", style=discord.ButtonStyle.success)
    async def ekle(self, interaction, button):
        WHITELIST_USERS.append(interaction.user.id)
        await interaction.response.send_message("✅ Whitelist eklendi", ephemeral=True)
    @discord.ui.button(label="➖ Çıkar", style=discord.ButtonStyle.danger)
    async def cikar(self, interaction, button):
        if interaction.user.id in WHITELIST_USERS:
            WHITELIST_USERS.remove(interaction.user.id)
        await interaction.response.send_message("❌ Whitelist çıkarıldı", ephemeral=True)
    @discord.ui.button(label="📋 Liste", style=discord.ButtonStyle.primary)
    async def liste(self, interaction, button):
        text = "\n".join(str(i) for i in WHITELIST_USERS)
        await interaction.response.send_message(f"```{text}```", ephemeral=True)

# ================= GUARD EVENTLERİ =================
@bot.event
async def on_webhooks_update(channel):
    async for entry in channel.guild.audit_logs(limit=1):
        if whitelist_mi(entry.user): return
        for wh in await channel.webhooks():
            await wh.delete()
        await ceza(entry.user, "Webhook Guard")
        stats["webhook"] += 1
        await log(channel.guild, "🛑 Webhook Guard", entry.user.mention)

@bot.event
async def on_member_ban(guild, user):
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        if whitelist_mi(entry.user): return
        await guild.unban(user)
        await ceza(entry.user, "Ban Guard")
        stats["ban"] += 1
        kaydet("ban")
        saatlik_kaydet("ban")
        await log(guild, "🛑 Ban Guard", entry.user.mention)

@bot.event
async def on_member_join(member):
    if member.bot:
        async for entry in member.guild.audit_logs(limit=1):
            if whitelist_mi(entry.user): return
            await member.kick(reason="Bot Guard")
            await ceza(entry.user, "Bot Ekleme Guard")
            stats["bot"] += 1
            await log(member.guild, "🛑 Bot Guard", entry.user.mention)

@bot.event
async def on_member_update(before, after):
    if whitelist_mi(after): return
    for rol in after.roles:
        if rol not in before.roles:
            if rol.permissions.administrator or rol.permissions.manage_roles:
                await after.remove_roles(rol)
                async for entry in after.guild.audit_logs(limit=1):
                    await ceza(entry.user, "Yetki Yükseltme Guard")
                    stats["yetki"] += 1
                    await log(after.guild, "🛑 Yetki Guard", entry.user.mention)

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(limit=1):
        if whitelist_mi(entry.user): return
        if anti_nuke_check(entry.user.id):
            await savunma_modu(channel.guild, "Kanal Silme Spike")
        await cezalandir(entry.user, "Kanal Silme Guard")
        stats["kanal"] += 1
        kaydet("kanal")
        saatlik_kaydet("kanal")

@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(limit=1):
        if whitelist_mi(entry.user): return
        if anti_nuke_check(entry.user.id):
            await savunma_modu(role.guild, "Rol Silme Spike")
        await cezalandir(entry.user, "Rol Silme Guard")
        stats["rol"] += 1
        kaydet("rol")
        saatlik_kaydet("rol")

# ================= KOMUTLAR =================
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Gecikme: {round(bot.latency*1000)}ms")

@bot.command(name="serverinfo")
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"{guild.name} Bilgileri", color=discord.Color.blue(), timestamp=datetime.datetime.utcnow())
    embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
    embed.add_field(name="Sunucu ID", value=guild.id, inline=True)
    embed.add_field(name="Üye Sayısı", value=guild.member_count, inline=True)
    embed.add_field(name="Rol Sayısı", value=len(guild.roles), inline=True)
    embed.add_field(name="Kanallar", value=len(guild.channels), inline=True)
    embed.add_field(name="Oluşturulma", value=guild.created_at.strftime("%d/%m/%Y %H:%M"), inline=True)
    if guild.banner:
        embed.set_image(url=guild.banner.url)
    await ctx.send(embed=embed)

# Buradan itibaren diğer 60+ komut aynı mantıkla eklenebilir: !userinfo, !roles, !kick, !ban, !mute, !unmute, !rolver, !rolal, !kanaloluştur, !kanalsil, !temizle, !guardstats, !guardpanel, !whitelistpanel, !savunmapanel, daily/weekly/hourly stats vb.

# ================= BOT EVENTLERİ =================
@bot.event
async def on_ready():
    print(f"✅ Bot giriş yaptı: {bot.user} (ID: {bot.user.id})")

# ================= BOTU ÇALIŞTIR =================
bot.run(TOKEN)
