import discord
from discord.ext import commands
from discord import ui, ButtonStyle
import datetime, time, os, re, io, psutil
from collections import defaultdict, deque
from PIL import Image, ImageDraw, ImageFilter

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
PREFIX = "!"
LOG_CHANNEL = "ultra-guard-log"
TIMEOUT_MIN = 15
START_TIME = time.time()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.webhooks = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ================= DATA =================
WHITELIST_USERS = set()
WHITELIST_ROLES = {"Founder", "Owner", "Admin"}

GUARDS = {
    "everyone": True,
    "emoji": True,
    "link": True,
    "channel": True,
    "role": True,
    "webhook": True,
    "botraid": True
}

LIMITS = {
    "everyone": (3, 15),
    "emoji": (6, 10),
    "link": (3, 15)
}

trackers = {
    "everyone": defaultdict(lambda: deque()),
    "emoji": defaultdict(lambda: deque()),
    "link": defaultdict(lambda: deque())
}

guard_logs = deque(maxlen=200)

# ================= HELPERS =================
def is_whitelisted(member: discord.Member):
    if member.guild.owner_id == member.id:
        return True
    if member.id in WHITELIST_USERS:
        return True
    return any(r.name in WHITELIST_ROLES for r in member.roles)

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

async def punish(member, reason):
    try:
        await member.timeout(datetime.timedelta(minutes=TIMEOUT_MIN), reason=reason)
    except:
        pass

async def get_log_channel(guild):
    ch = discord.utils.get(guild.text_channels, name=LOG_CHANNEL)
    if not ch:
        ch = await guild.create_text_channel(LOG_CHANNEL)
    return ch

# ================= GIF CARD LOG =================
async def create_gif_card(member, title, reason):
    frames = []
    avatar_bytes = await member.display_avatar.replace(size=128).read()
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((96, 96))

    for i in range(8):
        base = Image.new("RGBA", (720, 240), (20+i*2, 20+i*2, 40+i*3))
        bg = base.filter(ImageFilter.GaussianBlur(4))
        draw = ImageDraw.Draw(bg)

        bg.paste(avatar, (30, 70), avatar)
        draw.text((150, 40), title, fill="white")
        draw.text((150, 95), f"Kullanıcı: {member}", fill="#cccccc")
        draw.text((150, 135), f"Sebep: {reason}", fill="#ff5555")

        frames.append(bg)

    buf = io.BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=120,
        loop=0
    )
    buf.seek(0)
    return buf

async def log_guard(guild, member, title, reason):
    ch = await get_log_channel(guild)
    gif = await create_gif_card(member, title, reason)
    await ch.send(file=discord.File(gif, "guard.gif"))
    guard_logs.appendleft(f"{title} | {member}")

# ================= BUTTON PANELS =================
class GuardPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle(self, interaction, guard):
        GUARDS[guard] = not GUARDS[guard]
        await interaction.response.send_message(
            f"🛡️ {guard.upper()} ➜ {'AÇIK' if GUARDS[guard] else 'KAPALI'}",
            ephemeral=True
        )

    @ui.button(label="EVERYONE", style=ButtonStyle.primary)
    async def everyone(self, i, b): await self.toggle(i, "everyone")

    @ui.button(label="EMOJI", style=ButtonStyle.primary)
    async def emoji(self, i, b): await self.toggle(i, "emoji")

    @ui.button(label="LINK", style=ButtonStyle.primary)
    async def link(self, i, b): await self.toggle(i, "link")

    @ui.button(label="BOT RAID", style=ButtonStyle.danger)
    async def botraid(self, i, b): await self.toggle(i, "botraid")


class WhitelistPanel(ui.View):
    def __init__(self, target):
        super().__init__(timeout=30)
        self.target = target

    @ui.button(label="✅ Ekle", style=ButtonStyle.success)
    async def add(self, i, b):
        WHITELIST_USERS.add(self.target.id)
        await i.response.send_message("Whitelist eklendi", ephemeral=True)

    @ui.button(label="❌ Sil", style=ButtonStyle.danger)
    async def remove(self, i, b):
        WHITELIST_USERS.discard(self.target.id)
        await i.response.send_message("Whitelist silindi", ephemeral=True)

# ================= EVENTS =================
@bot.event
async def on_ready():
    print("🛡️ ULTRA GUARD v8 AKTİF")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    uid = message.author.id
    c = message.content

    if GUARDS["everyone"] and ("@everyone" in c or "@here" in c) and not is_whitelisted(message.author):
        if spike(trackers["everyone"], uid, *LIMITS["everyone"]):
            await punish(message.author, "Everyone Spam")
            await log_guard(message.guild, message.author, "EVERYONE SPAM", "Yetkisiz ping")

    if GUARDS["emoji"] and emoji_count(c) >= 6 and not is_whitelisted(message.author):
        if spike(trackers["emoji"], uid, *LIMITS["emoji"]):
            await punish(message.author, "Emoji Spam")
            await log_guard(message.guild, message.author, "EMOJI SPAM", "Emoji flood")

    if GUARDS["link"] and has_link(c) and not is_whitelisted(message.author):
        if spike(trackers["link"], uid, *LIMITS["link"]):
            await punish(message.author, "Link Spam")
            await log_guard(message.guild, message.author, "LINK SPAM", "Link flood")

    await bot.process_commands(message)

# ================= 30+ KOMUT =================
@bot.command()
async def guard(ctx): await ctx.send("🛡️ Guard Panel", view=GuardPanel())

@bot.command()
async def whitelist(ctx, user: discord.Member):
    await ctx.send(f"{user} whitelist", view=WhitelistPanel(user))

@bot.command()
async def ping(ctx): await ctx.send("🏓 Pong")

@bot.command()
async def uptime(ctx): await ctx.send(f"{int(time.time()-START_TIME)} saniye")

@bot.command()
async def cpu(ctx): await ctx.send(f"CPU {psutil.cpu_percent()}%")

@bot.command()
async def ram(ctx): await ctx.send(f"RAM {psutil.virtual_memory().percent}%")

@bot.command()
async def avatar(ctx, u: discord.Member=None):
    u = u or ctx.author
    await ctx.send(u.display_avatar.url)

@bot.command()
async def ban(ctx, m: discord.Member): await m.ban()

@bot.command()
async def kick(ctx, m: discord.Member): await m.kick()

@bot.command()
async def timeout(ctx, m: discord.Member, dk:int):
    await m.timeout(datetime.timedelta(minutes=dk))

@bot.command()
async def untimeout(ctx, m: discord.Member):
    await m.timeout(None)

@bot.command()
async def purge(ctx, s:int):
    await ctx.channel.purge(limit=s+1)

@bot.command()
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)

@bot.command()
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)

@bot.command()
async def slowmode(ctx, s:int):
    await ctx.channel.edit(slowmode_delay=s)

@bot.command()
async def say(ctx, *, t):
    await ctx.message.delete()
    await ctx.send(t)

@bot.command()
async def serverinfo(ctx):
    g=ctx.guild
    await ctx.send(f"{g.name} | {g.member_count} üye")

@bot.command()
async def userinfo(ctx, u:discord.Member=None):
    u=u or ctx.author
    await ctx.send(f"{u} | {u.id}")

@bot.command()
async def roleinfo(ctx, r:discord.Role):
    await ctx.send(f"{r.name} | {len(r.members)}")

@bot.command()
async def channelinfo(ctx):
    c=ctx.channel
    await ctx.send(f"{c.name} | {c.id}")

@bot.command()
async def guardlog(ctx):
    await ctx.send("\n".join(list(guard_logs)[:10]) or "Log yok")

# ================= RUN =================
bot.run(TOKEN)
