import discord
from discord.ext import commands
from discord import ui, ButtonStyle
import datetime, time, os, re, io, platform, psutil
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

# ================= CARD LOG =================
async def create_card(member, title, reason):
    avatar_bytes = await member.display_avatar.replace(size=128).read()
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((96, 96))

    base = Image.new("RGBA", (700, 220), (25, 25, 40))
    bg = base.filter(ImageFilter.GaussianBlur(6))
    bg.paste(base, (0, 0))

    draw = ImageDraw.Draw(bg)
    bg.paste(avatar, (30, 60), avatar)

    draw.text((150, 40), title, fill="white")
    draw.text((150, 90), f"Kullanıcı: {member}", fill="#cccccc")
    draw.text((150, 130), f"Sebep: {reason}", fill="#ff5555")

    buf = io.BytesIO()
    bg.save(buf, format="PNG")
    buf.seek(0)
    return buf

async def log_guard(guild, member, title, reason):
    ch = await get_log_channel(guild)
    card = await create_card(member, title, reason)
    await ch.send(file=discord.File(card, "guard.png"))
    guard_logs.appendleft(f"{title} | {member}")

# ================= BUTTON PANELS =================
class GuardPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle(self, interaction, guard):
        GUARDS[guard] = not GUARDS[guard]
        await interaction.response.send_message(
            f"🛡️ **{guard.upper()}** ➜ {'AÇIK' if GUARDS[guard] else 'KAPALI'}",
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
    def __init__(self, target: discord.Member):
        super().__init__(timeout=30)
        self.target = target

    @ui.button(label="✅ Whitelist Ekle", style=ButtonStyle.success)
    async def add(self, interaction, button):
        WHITELIST_USERS.add(self.target.id)
        await interaction.response.send_message(
            f"{self.target.mention} whitelist **eklendi**", ephemeral=True
        )

    @ui.button(label="❌ Whitelist Çıkar", style=ButtonStyle.danger)
    async def remove(self, interaction, button):
        WHITELIST_USERS.discard(self.target.id)
        await interaction.response.send_message(
            f"{self.target.mention} whitelist **çıkarıldı**", ephemeral=True
        )

# ================= EVENTS =================
@bot.event
async def on_ready():
    print("🛡️ ULTRA GUARD v7.1 AKTİF")

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

# ================= COMMANDS =================
@bot.command()
async def guard(ctx):
    await ctx.send("🛡️ **Ultra Guard Kontrol Paneli**", view=GuardPanel())

@bot.command()
async def whitelist(ctx, user: discord.Member):
    if not ctx.author.guild_permissions.administrator:
        return
    await ctx.send(
        f"👤 **{user} için whitelist işlemi**",
        view=WhitelistPanel(user)
    )

@bot.command()
async def stats(ctx):
    await ctx.send(
        f"🖥️ **Sistem Bilgisi**\n"
        f"CPU: {psutil.cpu_percent()}%\n"
        f"RAM: {psutil.virtual_memory().percent}%\n"
        f"Uptime: {int(time.time()-START_TIME)} sn"
    )

@bot.command()
async def avatar(ctx, user: discord.Member = None):
    user = user or ctx.author
    await ctx.send(user.display_avatar.url)

@bot.command()
async def guardlog(ctx):
    text = "\n".join(list(guard_logs)[:10]) or "Log yok"
    await ctx.send(f"```{text}```")

# ================= RUN =================
bot.run(TOKEN)
