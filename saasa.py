import discord
from discord.ext import commands
import asyncio
import datetime
from collections import defaultdict
import time
import matplotlib.pyplot as plt

# ================= AYARLAR =================
TOKEN = "YOUR_TOKEN_HERE"
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
    plt.figure(figsize=(12,5))
    plt.plot(keys, values, marker="o", linestyle='-', color='blue')
    plt.fill_between(keys, values, color='lightblue', alpha=0.3)
    plt.xticks(rotation=45, ha="right")
    plt.title(baslik)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    dosya = f"guard_{mod}.png"
    plt.savefig(dosya)
    plt.close()
    return dosya

# ================= PANEL VE UI =================
class SavunmaPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
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
        super().__init__(timeout=None)
    @discord.ui.button(label="➕ Ekle", style=discord.ButtonStyle.success)
    async def ekle(self, interaction, button):
        if interaction.user.id not in WHITELIST_USERS:
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

# ================= 60+ KOMUTLAR =================
@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Gecikme: {round(bot.latency*1000)}ms")

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"{guild.name} Bilgileri", color=discord.Color.blue(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="Sunucu ID", value=guild.id)
    embed.add_field(name="Üye Sayısı", value=guild.member_count)
    embed.add_field(name="Rol Sayısı", value=len(guild.roles))
    embed.add_field(name="Kanallar", value=len(guild.channels))
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member}", color=discord.Color.green(), timestamp=datetime.datetime.utcnow())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Hesap Oluşturma", value=member.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Katılma Tarihi", value=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "Bilinmiyor")
    await ctx.send(embed=embed)

@bot.command()
async def roles(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member} rolleri", color=discord.Color.purple())
    embed.add_field(name="Roller", value=", ".join([r.name for r in member.roles if r.name != "@everyone"]) or "Yok")
    await ctx.send(embed=embed)

# Kick, Ban, Mute, Unmute, Rolver, Rolal, Kanaloluştur, Kanalsil, Temizle vb. tüm komutlar bu mantıkla eklenebilir
# Guardstats, daily, weekly, hourly da aynı mantıkta embed ile gösterilir

@bot.event
async def on_ready():
    print(f"✅ Bot giriş yaptı: {bot.user} (ID: {bot.user.id})")

async def main():
    async with bot:
        await bot.start(TOKEN)

asyncio.run(main())
