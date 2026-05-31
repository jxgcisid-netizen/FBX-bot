import os
import asyncio
import hashlib
import secrets
import time
import discord
from quart import Quart, jsonify, request, current_app
from quart_cors import cors
from database import get_conn, release_conn, db_get_guild_settings, db_update_guild_setting
import logging

logger = logging.getLogger("WebAPI")

app = Quart(__name__)
app = cors(app, 
    allow_origin="*",
    allow_headers=["Content-Type", "Authorization"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# ==================== 密码验证系统 ====================

PANEL_PASSWORD = os.getenv("PANEL_PASSWORD", "fbxwcnm")
_valid_tokens = {}

def generate_token():
    return secrets.token_hex(32)

def clean_expired_tokens():
    now = time.time()
    expired = [t for t, exp in _valid_tokens.items() if exp < now]
    for t in expired:
        del _valid_tokens[t]

# ==================== 全局认证中间件 ====================

@app.before_request
async def check_auth():
    public_paths = ["/api/auth", "/api/health", "/api/verify-token"]
    if request.path in public_paths:
        return
    if request.method == "OPTIONS":
        return
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"success": False, "error": "未授权，请先登录"}), 401
    token = auth_header[7:]
    clean_expired_tokens()
    if token not in _valid_tokens:
        return jsonify({"success": False, "error": "token 无效或已过期"}), 401
    _valid_tokens[token] = time.time() + 86400

# ==================== 辅助函数 ====================

def get_guild_name_from_bot(guild_id: str) -> str:
    if hasattr(current_app, "bot"):
        guild = current_app.bot.get_guild(int(guild_id))
        if guild:
            return guild.name
    return "未知服务器"

# ==================== 认证接口 ====================

@app.route("/api/auth", methods=["POST", "OPTIONS"])
async def api_auth():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    try:
        data = await request.get_json()
        if not data or "password" not in data:
            return jsonify({"success": False, "error": "缺少密码"}), 400
        if data["password"] == PANEL_PASSWORD:
            token = generate_token()
            _valid_tokens[token] = time.time() + 86400
            clean_expired_tokens()
            logger.info("面板登录成功")
            return jsonify({"success": True, "token": token})
        else:
            logger.warning("面板登录失败：密码错误")
            return jsonify({"success": False, "error": "密码错误"}), 401
    except Exception as e:
        logger.error(f"Auth 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/verify-token", methods=["GET", "OPTIONS"])
async def api_verify_token():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "无效的 token"}), 401
        token = auth_header[7:]
        clean_expired_tokens()
        if token in _valid_tokens:
            _valid_tokens[token] = time.time() + 86400
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "token 已过期"}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 仪表盘 ====================

@app.route("/api/stats", methods=["GET", "OPTIONS"])
async def api_stats():
    if request.method == "OPTIONS":
        return jsonify({}), 200
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

@app.route("/api/guilds", methods=["GET", "OPTIONS"])
async def api_guilds():
    if request.method == "OPTIONS":
        return jsonify({}), 200
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
            data.append({
                "guild_id": row[0],
                "guild_name": get_guild_name_from_bot(row[0]),
                "user_count": row[1],
                "max_level": row[2]
            })
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"API guilds 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 排行榜 ====================

@app.route("/api/leaderboard/<guild_id>", methods=["GET", "OPTIONS"])
async def api_leaderboard(guild_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
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
            user_name = "未知用户"
            if hasattr(current_app, "bot"):
                guild = current_app.bot.get_guild(int(guild_id))
                member = guild.get_member(int(row[0])) if guild else None
                if member:
                    user_name = member.display_name
            data.append({
                "rank": i + 1,
                "user_id": row[0],
                "user_name": user_name,
                "level": row[1],
                "xp": row[2],
                "voice_xp": row[3]
            })
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"API leaderboard 错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 服务器预览 ====================

@app.route("/api/guilds/<guild_id>/preview", methods=["GET", "OPTIONS"])
async def api_guild_preview(guild_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503
    try:
        guild = current_app.bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"success": False, "error": "未找到该服务器"}), 404
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

# ==================== 获取频道列表 ====================

@app.route("/api/guilds/<guild_id>/channels", methods=["GET", "OPTIONS"])
async def api_guild_channels(guild_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503
    try:
        guild = current_app.bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"success": False, "error": "未找到该服务器"}), 404
        channels = []
        for ch in guild.text_channels:
            perms = ch.permissions_for(guild.me)
            if perms.send_messages and perms.read_messages:
                channels.append({
                    "id": str(ch.id),
                    "name": ch.name,
                    "category": ch.category.name if ch.category else None,
                    "topic": ch.topic[:100] if ch.topic else None,
                    "position": ch.position
                })
        channels.sort(key=lambda c: c["position"])
        return jsonify({"success": True, "data": channels})
    except Exception as e:
        logger.error(f"获取频道列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 获取成员列表 ====================

@app.route("/api/guilds/<guild_id>/members", methods=["GET", "OPTIONS"])
async def api_guild_members(guild_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503
    try:
        guild = current_app.bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"success": False, "error": "未找到该服务器"}), 404
        members = []
        for m in guild.members:
            if not m.bot:
                members.append({
                    "id": str(m.id),
                    "username": m.name,
                    "display_name": m.display_name,
                    "avatar_url": str(m.display_avatar.url) if m.display_avatar else None
                })
        members.sort(key=lambda x: x["display_name"].lower())
        return jsonify({"success": True, "data": members})
    except Exception as e:
        logger.error(f"获取成员列表失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 获取频道消息 ====================

@app.route("/api/channels/<channel_id>/messages", methods=["GET", "OPTIONS"])
async def api_channel_messages(channel_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503
    try:
        limit = int(request.args.get("limit", 20))
        limit = min(max(limit, 1), 100)
        channel = current_app.bot.get_channel(int(channel_id))
        if not channel:
            return jsonify({"success": False, "error": "未找到该频道"}), 404
        perms = channel.permissions_for(channel.guild.me)
        if not perms.read_messages or not perms.read_message_history:
            return jsonify({"success": False, "error": "机器人无读取权限"}), 403
        messages = []
        async for msg in channel.history(limit=limit):
            attachments = []
            for att in msg.attachments:
                attachments.append({
                    "filename": att.filename,
                    "url": att.url,
                    "size": att.size
                })
            messages.append({
                "id": str(msg.id),
                "author": msg.author.display_name,
                "author_id": str(msg.author.id),
                "avatar_url": str(msg.author.display_avatar.url) if msg.author.display_avatar else None,
                "color": str(msg.author.color) if msg.author.color.value else None,
                "content": msg.content if msg.content else "(空消息)",
                "timestamp": msg.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "attachments": attachments if attachments else None
            })
        return jsonify({"success": True, "data": messages})
    except Exception as e:
        logger.error(f"获取消息失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 发送消息 ====================

@app.route("/api/send-message", methods=["POST", "OPTIONS"])
async def api_send_message():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503
    try:
        data = await request.get_json()
        if not data:
            return jsonify({"success": False, "error": "请求体为空"}), 400
        channel_id = data.get("channel_id")
        content = data.get("content")
        embed_data = data.get("embed")
        if not channel_id:
            return jsonify({"success": False, "error": "缺少 channel_id"}), 400
        if not content:
            return jsonify({"success": False, "error": "缺少 content"}), 400
        if len(content) > 2000:
            return jsonify({"success": False, "error": "消息内容超过 2000 字符限制"}), 400
        channel = current_app.bot.get_channel(int(channel_id))
        if not channel:
            return jsonify({"success": False, "error": "未找到该频道"}), 404
        perms = channel.permissions_for(channel.guild.me)
        if not perms.send_messages:
            return jsonify({"success": False, "error": "机器人无发送消息权限"}), 403
        embed = None
        if embed_data and embed_data.get("enabled"):
            color_str = embed_data.get("color", "0x00b4d8").replace("#", "0x")
            try:
                color = int(color_str, 16)
            except ValueError:
                color = 0x00b4d8
            embed = discord.Embed(
                title=embed_data.get("title") or None,
                description=embed_data.get("description") or None,
                color=color
            )
            if embed_data.get("footer"):
                embed.set_footer(text=embed_data["footer"])
            if embed_data.get("thumbnail_url"):
                try:
                    embed.set_thumbnail(url=embed_data["thumbnail_url"])
                except Exception:
                    pass
        sent = await channel.send(content=content, embed=embed)
        logger.info(f"面板发送消息: #{channel.name} in {channel.guild.name}")
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
    except discord.HTTPException as e:
        logger.error(f"Discord HTTP 错误: {e}")
        return jsonify({"success": False, "error": f"Discord API 错误: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ==================== 服务器设置 ====================

@app.route("/api/settings/<guild_id>", methods=["GET", "POST", "OPTIONS"])
async def api_settings(guild_id):
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if request.method == "GET":
        try:
            settings = db_get_guild_settings(guild_id)
            return jsonify({"success": True, "data": settings})
        except Exception as e:
            logger.error(f"获取设置失败: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    elif request.method == "POST":
        try:
            data = await request.get_json()
            if not data:
                return jsonify({"success": False, "error": "请求体为空"}), 400
            updated = []
            if "xp_rate" in data:
                rate = max(0.1, min(float(data["xp_rate"]), 10.0))
                db_update_guild_setting(guild_id, "xp_rate", rate)
                updated.append(f"xp_rate={rate}")
            if "voice_xp_rate" in data:
                rate = max(0.1, min(float(data["voice_xp_rate"]), 10.0))
                db_update_guild_setting(guild_id, "voice_xp_rate", rate)
                updated.append(f"voice_xp_rate={rate}")
            logger.info(f"设置已更新: guild={guild_id}, {', '.join(updated)}")
            return jsonify({
                "success": True,
                "message": "设置已更新",
                "updated": updated
            })
        except ValueError as e:
            return jsonify({"success": False, "error": f"数值格式错误: {str(e)}"}), 400
        except Exception as e:
            logger.error(f"更新设置失败: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

# ==================== Bot 控制 ====================

@app.route("/api/stop-bot", methods=["POST", "OPTIONS"])
async def api_stop_bot():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503
    try:
        bot = current_app.bot
        if not bot.is_ready():
            return jsonify({"success": False, "error": "Bot 已经是离线状态"}), 400
        await bot.close()
        logger.warning("⚠️ Bot 已通过面板停止")
        return jsonify({"success": True, "message": "Bot 已停止"})
    except Exception as e:
        logger.error(f"停止 Bot 失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/start-bot", methods=["POST", "OPTIONS"])
async def api_start_bot():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 实例不存在"}), 503
    try:
        bot = current_app.bot
        if bot.is_ready():
            return jsonify({"success": False, "error": "Bot 已经在线"}), 400
        async def start_bot_task():
            try:
                await bot.start(os.getenv("DISCORD_TOKEN"))
            except Exception as e:
                logger.error(f"Bot 启动失败: {e}")
        asyncio.create_task(start_bot_task())
        logger.info("🔄 Bot 正在重新连接...")
        return jsonify({"success": True, "message": "Bot 正在启动，请稍候..."})
    except Exception as e:
        logger.error(f"启动 Bot 失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/bot-status", methods=["GET", "OPTIONS"])
async def api_bot_status():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503
    bot = current_app.bot
    return jsonify({
        "success": True,
        "data": {
            "is_ready": bot.is_ready(),
            "user": str(bot.user) if bot.user else None,
            "guilds_count": len(bot.guilds),
            "latency_ms": round(bot.latency * 1000, 1) if bot.is_ready() else None
        }
    })

# ==================== 健康检查 ====================

@app.route("/api/health", methods=["GET", "OPTIONS"])
async def api_health():
    if request.method == "OPTIONS":
        return jsonify({}), 200
    bot_connected = False
    if hasattr(current_app, "bot") and current_app.bot:
        bot_connected = current_app.bot.is_ready()
    return jsonify({
        "success": True,
        "status": "running",
        "bot_connected": bot_connected,
        "active_tokens": len(_valid_tokens)
    })
