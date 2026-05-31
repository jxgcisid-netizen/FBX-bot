import os
import logging
import platform
import discord
from discord.ext import commands
from PIL import ImageFont

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DiscordBot")

# ==================== 令牌 ====================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    logger.error("请设置 DISCORD_TOKEN 环境变量")
    exit(1)

# ==================== 字体路径 ====================
system = platform.system()
if system == "Windows":
    FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
    FONT_REGULAR = "C:/Windows/Fonts/arial.ttf"
elif system == "Darwin":
    FONT_BOLD = "/System/Library/Fonts/Helvetica.ttc"
    FONT_REGULAR = "/System/Library/Fonts/Helvetica.ttc"
elif system == "Linux":
    FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
    FONT_REGULAR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

# ==================== 颜色常量 ====================
TEAL = (65, 183, 183)
TEAL_DARK = (45, 130, 130)
TEAL_DIM = (45, 100, 100)
RED = (200, 60, 60)
RED_DARK = (140, 35, 35)
RED_DIM = (100, 30, 30)
GOLD = (255, 215, 0)
SILVER = (192, 192, 192)
BRONZE = (205, 127, 50)
RANK_COLORS = {1: GOLD, 2: SILVER, 3: BRONZE}
RANK_BG = {1: (55, 48, 10), 2: (42, 47, 58), 3: (52, 32, 12)}
RANK_BAR = {1: (255, 200, 0), 2: (180, 190, 210), 3: (200, 110, 50)}

# ==================== 字体缓存 ====================
_font_cache = {}

def get_font(size, bold=True):
    cache_key = f"{bold}_{size}"
    if cache_key in _font_cache:
        return _font_cache[cache_key]
    font_path = FONT_BOLD if bold else FONT_REGULAR
    try:
        if os.path.exists(font_path):
            font = ImageFont.truetype(font_path, size)
            _font_cache[cache_key] = font
            return font
    except Exception:
        pass
    return ImageFont.load_default()

# ==================== Bot 初始化 ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.guilds = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    logger.info(f"已登录: {bot.user}")
    try:
        synced = await bot.tree.sync()
        logger.info(f"斜杠命令已同步 ({len(synced)} 个)")
    except Exception as e:
        logger.error(f"同步命令失败: {e}")


async def load_modules():
    import events as ev
    import cogs as cog
    import tasks as tsk
    await ev.setup(bot)
    await cog.setup(bot)
    bot.loop.create_task(tsk.start_counter_updater(bot))
    logger.info("所有模块加载完成")


@bot.event
async def setup_hook():
    await load_modules()

    # 将 bot 挂载到 Quart app 上，实现资源共享
    from web_api import app as quart_app
    quart_app.bot = bot

    # 融入 discord.py 的 asyncio 事件循环
    import uvicorn
    config = uvicorn.Config(quart_app, host="0.0.0.0", port=8080, log_level="warning")
    server = uvicorn.Server(config)
    bot.loop.create_task(server.serve())
    logger.info("Web API (Quart) 已并入主 asyncio 事件循环 (port 8080)")


# ==================== 启动入口 ====================
if __name__ == "__main__":
    from database import init_db
    init_db()
    bot.run(TOKEN)
