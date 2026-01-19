import discord
from discord.ext import commands
import datetime
import time
from collections import defaultdict
import matplotlib.pyplot as plt
# ================= AUTO TIMEOUT =================
SPAM_LIMIT = 3
SPAM_TIMEOUT_DK = 15

last_messages = {}  # {user_id: {"content": str, "count": int}}

# ================= AYARLAR =================
TOKEN = "TOKEN_BOT_HERE"
PREFIX = "!"
LOG_KANAL = "mod-log"
TIMEOUT_DK = 1

# ================= WHITELIST =================
WHITELIST_USERS = []
WHITELIST_ROLES = ["Admin", "Founder"]

# ================= İSTATİSTİK =================
stats = defaultdict(int)
daily_stats = defaultdict(int)
weekly_stats = defaultdict(int)
hourly_stats = defaultdict(int)

# ================= INTENTS =================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ================= YARDIMCI =================
def whitelist_mi(member):
    if member.guild.owner_id == member.id:
        return True
    if member.id in WHITELIST_USERS:
        return True
    for r in member.roles:
        if r.name in WHITELIST_ROLES:
            return True
    return False

async def log(guild, title, desc):
    kanal = discord.utils.get(guild.text_channels, name=LOG_KANAL)
    if not kanal:
        kanal = await guild.create_text_channel(LOG_KANAL)
    embed = discord.Embed(title=title, description=desc, color=discord.Color.red())
    await kanal.send(embed=embed)

def kaydet(event):
    gun = datetime.date.today().isoformat()
    hafta = datetime.date.today().strftime("%Y-%W")
    saat = datetime.datetime.now().strftime("%Y-%m-%d %H")
    daily_stats[f"{gun}-{event}"] += 1
    weekly_stats[f"{hafta}-{event}"] += 1
    hourly_stats[f"{saat}-{event}"] += 1
    stats[event] += 1

# ================= GRAFİK =================
def grafik_olustur(data, baslik, dosya):
    plt.figure(figsize=(10,4))
    plt.plot(list(data.keys())[-20:], list(data.values())[-20:], marker="o")
    plt.xticks(rotation=45, ha="right")
    plt.title(baslik)
    plt.tight_layout()
    plt.savefig(dosya)
    plt.close()

# ================= READY =================
@bot.event
async def on_ready():
    print(f"✅ Giriş yapıldı: {bot.user}")

# ================= KOMUTLAR =================

@bot.command()
async def ping(ctx):
    await ctx.send(f"🏓 Pong: {round(bot.latency*1000)}ms")

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(member.display_avatar.url)

@bot.command()
async def banner(ctx, member: discord.Member = None):
    member = member or ctx.author
    user = await bot.fetch_user(member.id)
    if user.banner:
        await ctx.send(user.banner.url)
    else:
        await ctx.send("❌ Banner yok")

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=str(member), color=discord.Color.blue())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Katılım", value=member.joined_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Hesap", value=member.created_at.strftime("%d/%m/%Y"))
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    embed = discord.Embed(title=g.name, color=discord.Color.green())
    embed.add_field(name="Üyeler", value=g.member_count)
    embed.add_field(name="Roller", value=len(g.roles))
    embed.add_field(name="Kanallar", value=len(g.channels))
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def temizle(ctx, amount: int):
    await ctx.channel.purge(limit=amount+1)
    await ctx.send(f"🧹 {amount} mesaj silindi", delete_after=3)

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="Yok"):
    await member.kick(reason=reason)
    kaydet("kick")
    await log(ctx.guild, "Kick", f"{member} | {reason}")
    await ctx.send("✅ Kicklendi")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="Yok"):
    await member.ban(reason=reason)
    kaydet("ban")
    await log(ctx.guild, "Ban", f"{member} | {reason}")
    await ctx.send("⛔ Banlandı")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, dakika: int):
    await member.timeout(datetime.timedelta(minutes=dakika))
    kaydet("mute")
    await ctx.send("🔇 Susturuldu")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send("🔊 Susturma kaldırıldı")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def rolver(ctx, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await ctx.send("✅ Rol verildi")

@bot.command()
@commands.has_permissions(manage_roles=True)
async def rolal(ctx, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await ctx.send("❌ Rol alındı")

@bot.command()
async def roles(ctx):
    roles = ", ".join(r.name for r in ctx.guild.roles)
    await ctx.send(roles[:1900])

@bot.command()
@commands.has_permissions(manage_channels=True)
async def kanalolustur(ctx, *, name):
    await ctx.guild.create_text_channel(name)
    await ctx.send("📁 Kanal oluşturuldu")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def kanalsil(ctx, channel: discord.TextChannel = None):
    channel = channel or ctx.channel
    await channel.delete()

@bot.command()
async def guardstats(ctx):
    embed = discord.Embed(title="📊 Guard Stats")
    for k,v in stats.items():
        embed.add_field(name=k, value=v)
    await ctx.send(embed=embed)

@bot.command()
async def daily(ctx):
    grafik_olustur(daily_stats, "Günlük", "daily.png")
    await ctx.send(file=discord.File("daily.png"))

@bot.command()
async def weekly(ctx):
    grafik_olustur(weekly_stats, "Haftalık", "weekly.png")
    await ctx.send(file=discord.File("weekly.png"))

@bot.command()
async def hourly(ctx):
    grafik_olustur(hourly_stats, "Saatlik", "hourly.png")
    await ctx.send(file=discord.File("hourly.png"))

@bot.command()
async def say(ctx, *, text):
    await ctx.send(text)
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    member = message.author

    # Whitelist kontrolü
    if whitelist_mi(member):
        await bot.process_commands(message)
        return

    uid = member.id
    content = message.content.strip().lower()

    if uid not in last_messages:
        last_messages[uid] = {"content": content, "count": 1}
    else:
        if last_messages[uid]["content"] == content:
            last_messages[uid]["count"] += 1
        else:
            last_messages[uid] = {"content": content, "count": 1}

    # Spam limiti aşılırsa
    if last_messages[uid]["count"] >= SPAM_LIMIT:
        try:
            await member.timeout(
                datetime.timedelta(minutes=SPAM_TIMEOUT_DK),
                reason="Spam: Aynı mesajı 3 kez gönderdi"
            )
            kaydet("auto-timeout")
            await log(
                message.guild,
                "⏱️ Auto Timeout",
                f"{member.mention} | Aynı mesajı 3 kez attı (15 dk)"
            )
            await message.channel.send(
                f"⛔ {member.mention} spam yaptığı için **15 dakika timeout** yedi."
            )
        except:
            pass

        last_messages.pop(uid, None)

    await bot.process_commands(message)

# ================= RUN =================
bot.run(TOKEN)
