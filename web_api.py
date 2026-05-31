from quart import Quart, jsonify, request, current_app
from quart_cors import cors
from database import get_conn, release_conn, db_get_guild_settings, db_update_guild_setting
import logging

logger = logging.getLogger("WebAPI")

app = Quart(__name__)
app = cors(app, allow_origin="*")  # 允许跨域

# ==================== 扩展：获取真实的服务器名称 ====================
def get_guild_name_from_bot(guild_id: str) -> str:
    """从共享的 bot 实例中获取服务器真实名称"""
    if hasattr(current_app, "bot"):
        guild = current_app.bot.get_guild(int(guild_id))
        if guild:
            return guild.name
    return "未知服务器"

# ==================== 仪表盘 ====================
@app.route("/api/stats")
async def api_stats():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT guild_id) FROM users")
        guild_count = cur.fetchone()[0]
        cur.execute("SELECT MAX(level) FROM users")
        max_level = cur.fetchone()[0] or 0
        cur.close()
        release_conn(conn)
        
        # 联动：可以拿到当前 Bot 实际所在的真实服务器数量
        active_guilds = len(current_app.bot.guilds) if hasattr(current_app, "bot") else guild_count
        
        return jsonify({
            "success": True,
            "data": {
                "total_users": user_count,
                "total_guilds": active_guilds, 
                "max_level": max_level
            }
        })
    except Exception as e:
        logger.error(f"API stats 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 服务器列表 ====================
@app.route("/api/guilds")
async def api_guilds():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT guild_id, COUNT(*) as user_count, MAX(level) as max_level
            FROM users GROUP BY guild_id ORDER BY user_count DESC
        """)
        rows = cur.fetchall()
        cur.close()
        release_conn(conn)
        
        data = []
        for row in rows:
            g_id = row[0]
            data.append({
                "guild_id": g_id,
                "guild_name": get_guild_name_from_bot(g_id), # 完美获取 Discord 服务器名字！
                "user_count": row[1],
                "max_level": row[2]
            })
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"API guilds 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 排行榜 ====================
@app.route("/api/leaderboard/<guild_id>")
async def api_leaderboard(guild_id):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, level, xp, voice_xp FROM users 
            WHERE guild_id = %s ORDER BY level DESC, xp DESC LIMIT 100
        """, (str(guild_id),))
        rows = cur.fetchall()
        cur.close()
        release_conn(conn)
        
        data = []
        for i, row in enumerate(rows):
            u_id = row[0]
            # 尝试获取用户名
            user_name = "未知用户"
            if hasattr(current_app, "bot"):
                guild = current_app.bot.get_guild(int(guild_id))
                member = guild.get_member(int(u_id)) if guild else None
                if member:
                    user_name = member.display_name

            data.append({
                "rank": i + 1,
                "user_id": u_id,
                "user_name": user_name,
                "level": row[1],
                "xp": row[2],
                "voice_xp": row[3]
            })
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"API leaderboard 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 服务器设置 ====================
@app.route("/api/settings/<guild_id>", methods=["GET", "POST"])
async def api_settings(guild_id):
    if request.method == "GET":
        try:
            settings = db_get_guild_settings(guild_id)
            return jsonify({"success": True, "data": settings})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    elif request.method == "POST":
        try:
            data = await request.get_json()
            if "xp_rate" in data:
                db_update_guild_setting(guild_id, "xp_rate", max(0.1, min(float(data["xp_rate"]), 10.0)))
            if "voice_xp_rate" in data:
                db_update_guild_setting(guild_id, "voice_xp_rate", max(0.1, min(float(data["voice_xp_rate"]), 10.0)))
            return jsonify({"success": True, "message": "设置已更新"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/health")
async def api_health():
    return jsonify({"success": True, "status": "running"})

# ==================== 新增：Discord 消息发送 ====================

@app.route("/api/guilds/<guild_id>/channels", methods=["GET"])
async def api_guild_channels(guild_id):
    """获取服务器的文字频道列表"""
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503

    try:
        guild = current_app.bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"success": False, "error": "未找到该服务器"}), 404

        channels = []
        for ch in guild.text_channels:
            # 检查机器人是否有发送权限
            perms = ch.permissions_for(guild.me)
            if perms.send_messages and perms.read_messages:
                channels.append({
                    "id": str(ch.id),
                    "name": ch.name,
                    "category": ch.category.name if ch.category else None,
                    "topic": ch.topic[:100] if ch.topic else None,
                    "position": ch.position
                })

        # 按位置排序
        channels.sort(key=lambda c: c["position"])
        return jsonify({"success": True, "data": channels})
    except Exception as e:
        logger.error(f"获取频道列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/send-message", methods=["POST"])
async def api_send_message():
    """通过机器人向指定频道发送消息"""
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503

    try:
        data = await request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400

        channel_id = data.get("channel_id")
        content = data.get("content")
        embed_data = data.get("embed")

        if not channel_id or not content:
            return jsonify({"success": False, "error": "缺少 channel_id 或 content"}), 400

        if len(content) > 2000:
            return jsonify({"success": False, "error": "消息内容超过 2000 字符限制"}), 400

        channel = current_app.bot.get_channel(int(channel_id))
        if not channel:
            return jsonify({"success": False, "error": "未找到该频道"}), 404

        # 检查权限
        perms = channel.permissions_for(channel.guild.me)
        if not perms.send_messages:
            return jsonify({"success": False, "error": "机器人无发送权限"}), 403

        # 构建 embed
        embed = None
        if embed_data and embed_data.get("enabled"):
            embed = discord.Embed(
                title=embed_data.get("title") or None,
                description=embed_data.get("description") or None,
                color=int(embed_data.get("color", "0x00b4d8").replace("0x", ""), 16)
            )
            if embed_data.get("footer"):
                embed.set_footer(text=embed_data["footer"])
            if embed_data.get("thumbnail_url"):
                embed.set_thumbnail(url=embed_data["thumbnail_url"])

        # 发送消息
        sent = await channel.send(content=content, embed=embed)

        return jsonify({
            "success": True,
            "message": "消息已发送",
            "data": {
                "message_id": str(sent.id),
                "channel_id": str(channel_id),
                "channel_name": channel.name,
                "guild_name": channel.guild.name
            }
        })
    except discord.Forbidden:
        return jsonify({"success": False, "error": "机器人权限不足"}), 403
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/guilds/<guild_id>/preview", methods=["GET"])
async def api_guild_preview(guild_id):
    """获取服务器的基本信息预览"""
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503

    try:
        guild = current_app.bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"success": False, "error": "未找到该服务器"}), 404

        # 在线人数
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)

        return jsonify({
            "success": True,
            "data": {
                "name": guild.name,
                "id": str(guild.id),
                "member_count": guild.member_count,
                "online_count": online,
                "text_channels": len(guild.text_channels),
                "voice_channels": len(guild.voice_channels),
                "roles_count": len(guild.roles),
                "created_at": guild.created_at.isoformat(),
                "icon_url": str(guild.icon.url) if guild.icon else None
            }
        })
    except Exception as e:
        logger.error(f"获取服务器预览失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
