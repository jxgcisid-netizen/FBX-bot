import discord
from discord import app_commands, Interaction
from discord.ext import commands
import asyncio
import re
from main import logger

SEARCH_SOURCES = [
    app_commands.Choice(name="自动 (YT > B站)", value="auto"),
    app_commands.Choice(name="YouTube", value="ytsearch"),
    app_commands.Choice(name="Bilibili", value="bili"),
    app_commands.Choice(name="SoundCloud", value="scsearch"),
]


def extract_bilibili_id(query: str) -> str | None:
    patterns = [
        r'bilibili\.com/video/(BV\w+)',
        r'bilibili\.com/video/(av\d+)',
        r'b23\.tv/(\w+)',
        r'(BV\w{10})',
        r'(av\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


class MusicPlayer:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.queue: list = []
        self.current = None
        self.loop_mode = "off"

    def add(self, track):
        self.queue.append(track)

    def get_next(self):
        if self.loop_mode == "track" and self.current:
            return self.current
        if self.loop_mode == "queue" and self.current:
            self.queue.append(self.current)
        if self.queue:
            self.current = self.queue.pop(0)
            return self.current
        self.current = None
        return None

    def clear(self):
        self.queue.clear()
        self.current = None

    def shuffle(self):
        import random
        random.shuffle(self.queue)


class MusicCommands(commands.GroupCog, name="music"):
    def __init__(self, bot):
        self.bot = bot
        self.players: dict[int, MusicPlayer] = {}

    def get_player(self, guild_id: int) -> MusicPlayer:
        if guild_id not in self.players:
            self.players[guild_id] = MusicPlayer(guild_id)
        return self.players[guild_id]

    async def ensure_voice(self, interaction: Interaction) -> bool:
        if not interaction.user.voice:
            await interaction.followup.send("需要先加入一个语音频道", ephemeral=True)
            return False
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()
        elif interaction.guild.voice_client.channel != interaction.user.voice.channel:
            await interaction.guild.voice_client.move_to(interaction.user.voice.channel)
        return True

    async def get_audio_url(self, query: str, source: str = "ytsearch") -> str | None:
        try:
            cmd = ["yt-dlp", "-f", "bestaudio/best", "--get-url", "--no-playlist", "--quiet"]
            if source == "bili" or "bilibili.com" in query or "b23.tv" in query:
                cmd.append(query)
            else:
                cmd.append(f"ytsearch:{query}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=12)
            if stdout and stdout.strip():
                return stdout.decode().strip()
            return None
        except asyncio.TimeoutError:
            logger.warning(f"获取音频URL超时: {query}")
            return None
        except Exception as e:
            logger.error(f"获取音频URL失败: {e}")
            return None

    async def get_video_info(self, query: str, source: str = "ytsearch") -> dict:
        try:
            cmd = ["yt-dlp", "--get-title", "--no-playlist", "--quiet"]
            if source == "bili" or "bilibili.com" in query or "b23.tv" in query:
                cmd.append(query)
            else:
                cmd.append(f"ytsearch:{query}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
            if stdout and stdout.strip():
                return {"title": stdout.decode().strip()}
            return {"title": query}
        except asyncio.TimeoutError:
            logger.warning(f"获取视频信息超时: {query}")
            return {"title": query}
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            return {"title": query}

    @app_commands.command(name="play", description="播放一首歌曲")
    @app_commands.choices(source=SEARCH_SOURCES)
    async def play(self, interaction: Interaction, query: str, source: str = "auto"):
        await interaction.response.defer()

        if not await self.ensure_voice(interaction):
            return

        if "youtube.com" in query or "youtu.be" in query:
            actual_source = "ytsearch"
        elif "soundcloud.com" in query:
            actual_source = "scsearch"
        elif "bilibili.com" in query or "b23.tv" in query or extract_bilibili_id(query):
            actual_source = "bili"
        elif source != "auto":
            actual_source = source
        else:
            actual_source = "ytsearch"

        audio_url = await self.get_audio_url(query, actual_source)
        if not audio_url:
            await interaction.followup.send("未找到歌曲或获取音频失败")
            return

        info = await self.get_video_info(query, actual_source)
        title = info.get("title", query)

        player = self.get_player(interaction.guild.id)
        vc = interaction.guild.voice_client

        if vc and vc.is_playing():
            player.add({"url": audio_url, "title": title})
            await interaction.followup.send(f"已加入队列: **{title}**")
            return

        try:
            source = discord.FFmpegPCMAudio(
                audio_url,
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
            )
            vc.play(source, after=lambda e: self.bot.loop.create_task(self.play_next(interaction.guild.id)))
            player.current = {"url": audio_url, "title": title}
            await interaction.followup.send(f"正在播放: **{title}**")
        except Exception as e:
            logger.error(f"播放失败: {e}")
            await interaction.followup.send("播放失败，请稍后再试")

    async def play_next(self, guild_id: int):
        player = self.get_player(guild_id)
        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            return

        next_track = player.get_next()
        if next_track:
            try:
                source = discord.FFmpegPCMAudio(
                    next_track["url"],
                    before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
                )
                guild.voice_client.play(
                    source,
                    after=lambda e: self.bot.loop.create_task(self.play_next(guild_id))
                )
            except:
                pass
        else:
            await asyncio.sleep(60)
            if guild.voice_client and not guild.voice_client.is_playing():
                await guild.voice_client.disconnect()

    @app_commands.command(name="skip", description="跳过当前歌曲")
    async def skip(self, interaction: Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("已跳过")
        else:
            await interaction.response.send_message("当前没有正在播放的歌曲")

    @app_commands.command(name="stop", description="停止播放并离开")
    async def stop(self, interaction: Interaction):
        player = self.get_player(interaction.guild.id)
        player.clear()
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
        await interaction.response.send_message("已停止播放")

    @app_commands.command(name="queue", description="查看播放队列")
    async def queue(self, interaction: Interaction):
        player = self.get_player(interaction.guild.id)
        lines = []
        if player.current:
            lines.append(f"正在播放: {player.current['title']}")
        lines.append(f"队列: {len(player.queue)} 首")
        for i, t in enumerate(player.queue[:10], 1):
            lines.append(f"  {i}. {t['title']}")
        if len(player.queue) > 10:
            lines.append(f"  ...还有 {len(player.queue) - 10} 首")
        lines.append(f"循环模式: {player.loop_mode}")
        await interaction.response.send_message("\n".join(lines))

    @app_commands.command(name="pause", description="暂停播放")
    async def pause(self, interaction: Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.send_message("已暂停")
        else:
            await interaction.response.send_message("当前没有正在播放的歌曲")

    @app_commands.command(name="resume", description="继续播放")
    async def resume(self, interaction: Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.send_message("继续播放")
        else:
            await interaction.response.send_message("当前没有暂停的歌曲")

    @app_commands.command(name="loop", description="设置循环模式")
    @app_commands.choices(mode=[
        app_commands.Choice(name="关闭", value="off"),
        app_commands.Choice(name="单曲循环", value="track"),
        app_commands.Choice(name="队列循环", value="queue"),
    ])
    async def loop(self, interaction: Interaction, mode: str):
        player = self.get_player(interaction.guild.id)
        player.loop_mode = mode
        names = {"off": "关闭", "track": "单曲循环", "queue": "队列循环"}
        await interaction.response.send_message(f"循环模式: **{names[mode]}**")

    @app_commands.command(name="volume", description="设置音量")
    async def volume(self, interaction: Interaction, level: int):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.source.volume = max(0, min(level, 100)) / 100
            await interaction.response.send_message(f"音量: **{level}%**")
        else:
            await interaction.response.send_message("当前没有播放中的歌曲")

    @app_commands.command(name="shuffle", description="随机打乱队列")
    async def shuffle_cmd(self, interaction: Interaction):
        player = self.get_player(interaction.guild.id)
        if not player.queue:
            await interaction.response.send_message("队列为空")
            return
        player.shuffle()
        await interaction.response.send_message("队列已随机打乱")

    @app_commands.command(name="nowplaying", description="当前播放")
    async def nowplaying(self, interaction: Interaction):
        player = self.get_player(interaction.guild.id)
        if player.current:
            await interaction.response.send_message(f"**{player.current['title']}**")
        else:
            await interaction.response.send_message("当前没有正在播放的歌曲")


async def setup(bot):
    await bot.add_cog(MusicCommands(bot))
