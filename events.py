import asyncio
import random
import discord
from datetime import datetime
from main import logger
from database import get_conn as db_conn, release_conn as db_release

_xp_cooldown = {}
_voice_tracker = {}
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
            # 等级奖励角色
            role_id = db_get_level_role(gid, user_data["level"])
            if role_id:
                role = message.guild.get_role(int(role_id))
                if role:
                    try:
                        await message.author.add_roles(role)
                    except discord.Forbidden:
                        pass

            # 查升级公告频道
            conn = db_conn()
            cur = conn.cursor()
            cur.execute("SELECT levelup_channel_id FROM guild_settings WHERE guild_id = %s", (gid,))
            row = cur.fetchone()
            cur.close()
            db_release(conn)

            target_ch = message.channel
            if row and row[0]:
                ch = message.guild.get_channel(int(row[0]))
                if ch:
                    target_ch = ch

            embed = discord.Embed(
                title="🎉 等级提升！",
                description=f"{message.author.mention} → **{user_data['level']}级**！",
                color=discord.Color.gold()
            )
            await target_ch.send(embed=embed)

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
                        # 等级奖励角色
                        role_id = db_get_level_role(gid, data["level"])
                        if role_id:
                            role = member.guild.get_role(int(role_id))
                            if role:
                                try:
                                    await member.add_roles(role)
                                except Exception:
                                    pass

                        # 查升级公告频道
                        conn = db_conn()
                        cur = conn.cursor()
                        cur.execute("SELECT levelup_channel_id FROM guild_settings WHERE guild_id = %s", (gid,))
                        row = cur.fetchone()
                        cur.close()
                        db_release(conn)

                        target_ch = member.guild.system_channel or member.guild.text_channels[0]
                        if row and row[0]:
                            ch = member.guild.get_channel(int(row[0]))
                            if ch:
                                target_ch = ch

                        embed = discord.Embed(
                            title="🎉 等级提升！",
                            description=f"{member.mention} → **{data['level']}级**！",
                            color=discord.Color.gold()
                        )
                        await target_ch.send(embed=embed)

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

    # ==================== 成员事件 ====================
    @bot.event
    async def on_member_join(member):
        from database import db_get_welcome_channel
        from cards import create_welcome_card
        ch_id = db_get_welcome_channel(str(member.guild.id))
        if not ch_id:
            return
        ch = member.guild.get_channel(int(ch_id))
        if not ch:
            return
        try:
            buf = await create_welcome_card(member, member.guild.member_count)
            await ch.send(file=discord.File(buf, "welcome.png"))
        except Exception as e:
            logger.error(f"欢迎卡片失败: {e}")
            embed = discord.Embed(
                title="👋 欢迎！",
                description=f"欢迎 {member.mention}！第 **{member.guild.member_count}** 位成员",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await ch.send(embed=embed)

    @bot.event
    async def on_member_remove(member):
        from database import db_get_welcome_channel
        from cards import create_goodbye_card
        ch_id = db_get_welcome_channel(str(member.guild.id))
        if not ch_id:
            return
        ch = member.guild.get_channel(int(ch_id))
        if not ch:
            return
        try:
            buf = await create_goodbye_card(member, member.guild.member_count)
            await ch.send(file=discord.File(buf, "goodbye.png"))
        except Exception as e:
            logger.error(f"告别卡片失败: {e}")
            embed = discord.Embed(
                title="👋 再见",
                description=f"{member.display_name} 离开了，还剩 **{member.guild.member_count}** 人",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await ch.send(embed=embed)

    # ==================== 消息日志事件 ====================
    @bot.event
    async def on_message_delete(message):
        if message.author.bot:
            return
        from database import db_get_log_channel
        ch_id = db_get_log_channel(str(message.guild.id), "message_log_channel")
        if ch_id:
            ch = message.guild.get_channel(int(ch_id))
            if ch:
                embed = discord.Embed(
                    title="🗑️ 消息删除",
                    description=f"{message.channel.mention} | {message.author.mention}\n{message.content[:500]}",
                    color=discord.Color.red(),
                    timestamp=datetime.now()
                )
                await ch.send(embed=embed)

    @bot.event
    async def on_message_edit(before, after):
        if before.author.bot or before.content == after.content:
            return
        from database import db_get_log_channel
        ch_id = db_get_log_channel(str(before.guild.id), "message_log_channel")
        if ch_id:
            ch = before.guild.get_channel(int(ch_id))
            if ch:
                embed = discord.Embed(
                    title="✏️ 消息编辑",
                    description=f"{before.channel.mention} | {before.author.mention}\n**前:** {before.content[:300]}\n**后:** {after.content[:300]}",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                await ch.send(embed=embed)

    # ==================== 反应角色事件 ====================
    @bot.event
    async def on_raw_reaction_add(payload):
        if payload.user_id == bot.user.id:
            return
        from database import db_get_reaction_role
        row = db_get_reaction_role(payload.guild_id, payload.message_id, payload.emoji.name)
        if row:
            guild = bot.get_guild(payload.guild_id)
            role = guild.get_role(int(row["role_id"])) if guild else None
            member = guild.get_member(payload.user_id) if guild else None
            if role and member:
                try:
                    await member.add_roles(role)
                except:
                    pass

    @bot.event
    async def on_raw_reaction_remove(payload):
        from database import db_get_reaction_role
        row = db_get_reaction_role(payload.guild_id, payload.message_id, payload.emoji.name)
        if row:
            guild = bot.get_guild(payload.guild_id)
            role = guild.get_role(int(row["role_id"])) if guild else None
            member = guild.get_member(payload.user_id) if guild else None
            if role and member:
                try:
                    await member.remove_roles(role)
                except:
                    pass
