import asyncio
import random
import discord
from datetime import datetime
from main import logger

_xp_cooldown = {}
_voice_tracker = {}
# 添加锁
_xp_lock = asyncio.Lock()
_voice_lock = asyncio.Lock()


async def setup(bot):
    # ==================== 消息事件 ====================
    @bot.event
    async def on_message(message):
        if message.author.bot or not message.guild:
            return

        from database import db_get_guild_settings, db_get_user, db_update_user, db_get_level_role, process_level_up

        gid = str(message.guild.id)
        uid = str(message.author.id)
        key = f"{gid}:{uid}"
        now = datetime.now()

        # 用锁保护 _xp_cooldown 的读写
        async with _xp_lock:
            if key in _xp_cooldown and (now - _xp_cooldown[key]).total_seconds() < 20:
                await bot.process_commands(message)
                return
            _xp_cooldown[key] = now

        settings = db_get_guild_settings(gid)
        user_data = db_get_user(gid, uid)
        user_data["xp"] += int(random.randint(15, 25) * settings["xp_rate"])
        user_data, gained = process_level_up(user_data)

        if gained > 0:
            role_id = db_get_level_role(gid, user_data["level"])
            if role_id:
                role = message.guild.get_role(int(role_id))
                if role:
                    try:
                        await message.author.add_roles(role)
                    except discord.Forbidden:
                        pass
            embed = discord.Embed(
                title="🎉 等级提升！",
                description=f"{message.author.mention} → **{user_data['level']}级**！",
                color=discord.Color.gold()
            )
            await message.channel.send(embed=embed, delete_after=10)

        db_update_user(gid, uid, user_data)
        await bot.process_commands(message)

    # ==================== 语音事件 ====================
    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.bot:
            return

        from database import (
            db_get_guild_settings, db_get_user, db_update_user,
            db_get_log_channel, db_get_level_role, process_level_up
        )

        gid = str(member.guild.id)

        # 加入语音
        if before.channel is None and after.channel is not None:
            async with _voice_lock:
                _voice_tracker[member.id] = datetime.now()
            ch_id = db_get_log_channel(gid, "voice_log_channel")
            if ch_id:
                ch = member.guild.get_channel(int(ch_id))
                if ch:
                    await ch.send(embed=discord.Embed(
                        title="🔊 加入语音",
                        description=f"{member.mention} → {after.channel.mention}",
                        color=discord.Color.green()
                    ))

        # 离开语音
        elif before.channel is not None and after.channel is None:
            async with _voice_lock:
                join_time = _voice_tracker.pop(member.id, None)
            if join_time:
                duration = (datetime.now() - join_time).total_seconds()
                if duration >= 60:
                    settings = db_get_guild_settings(gid)
                    xp_gain = int((duration / 60) * 5 * settings["voice_xp_rate"])
                    data = db_get_user(gid, member.id)
                    data["voice_xp"] += xp_gain
                    data["xp"] += xp_gain
                    data, gained = process_level_up(data)
                    if gained > 0:
                        role_id = db_get_level_role(gid, data["level"])
                        if role_id:
                            role = member.guild.get_role(int(role_id))
                            if role:
                                try:
                                    await member.add_roles(role)
                                except Exception:
                                    pass
                    db_update_user(gid, member.id, data)

            ch_id = db_get_log_channel(gid, "voice_log_channel")
            if ch_id:
                ch = member.guild.get_channel(int(ch_id))
                if ch:
                    await ch.send(embed=discord.Embed(
                        title="🔇 离开语音",
                        description=f"{member.mention} 离开 {before.channel.mention}",
                        color=discord.Color.red()
                    ))

    # ==================== 其余事件保持不变 ====================
    # （on_member_join、on_member_remove、on_message_delete 等）
    # ... 保持原样 ...
