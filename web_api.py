import os
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

# 控制面板密码（从环境变量读取，默认值仅用于开发）
PANEL_PASSWORD = os.getenv("PANEL_PASSWORD")

# 存储有效 token（简单内存实现，生产环境建议用 Redis）
_valid_tokens = {}  # {token: expire_timestamp}


def generate_token():
    """生成随机 token"""
    return secrets.token_hex(32)


def clean_expired_tokens():
    """清理过期 token"""
    now = time.time()
    expired = [t for t, exp in _valid_tokens.items() if exp < now]
    for t in expired:
        del _valid_tokens[t]


# ==================== 全局认证中间件 ====================

@app.before_request
async def check_auth():
    """检查除 auth/health/verify-token 外的所有请求是否带有效 token"""
    # 不需要验证的路径
    public_paths = ["/api/auth", "/api/health", "/api/verify-token"]
    if request.path in public_paths:
        return

    # 处理 OPTIONS 预检请求
    if request.method == "OPTIONS":
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"success": False, "error": "未授权，请先登录"}), 401

    token = auth_header[7:]
    clean_expired_tokens()

    if token not in _valid_tokens:
        return jsonify({"success": False, "error": "token 无效或已过期"}), 401

    # 刷新 token 有效期（每次请求延寿）
    _valid_tokens[token] = time.time() + 86400


# ==================== 获取真实的服务器名称 ====================

def get_guild_name_from_bot(guild_id: str) -> str:
    """从共享的 bot 实例中获取服务器真实名称"""
    if hasattr(current_app, "bot"):
        guild = current_app.bot.get_guild(int(guild_id))
        if guild:
            return guild.name
    return "未知服务器"


# ==================== 认证相关接口 ====================

@app.route("/api/auth", methods=["POST", "OPTIONS"])
async def api_auth():
    """验证密码并返回 token"""
    # 处理 CORS 预检请求
    if request.method == "OPTIONS":
        return jsonify({}), 200

    try:
        data = await request.get_json()
        if not data or "password" not in data:
            return jsonify({"success": False, "error": "缺少密码"}), 400

        password = data["password"]

        if password == PANEL_PASSWORD:
            # 生成 token，有效期 24 小时
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
    """验证 token 是否有效"""
    # 处理 CORS 预检请求
    if request.method == "OPTIONS":
        return jsonify({}), 200

    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"success": False, "error": "无效的 token"}), 401

        token = auth_header[7:]
        clean_expired_tokens()

        if token in _valid_tokens:
            # 刷新有效期
            _valid_tokens[token] = time.time() + 86400
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "token 已过期"}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 仪表盘 ====================

@app.route("/api/stats", methods=["GET", "OPTIONS"])
async def api_stats():
    # 处理 CORS 预检请求
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

        # 联动：拿到当前 Bot 实际所在的真实服务器数量
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
    # 处理 CORS 预检请求
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
            g_id = row[0]
            data.append({
                "guild_id": g_id,
                "guild_name": get_guild_name_from_bot(g_id),
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
    # 处理 CORS 预检请求
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


# ==================== 服务器预览 ====================

@app.route("/api/guilds/<guild_id>/preview", methods=["GET", "OPTIONS"])
async def api_guild_preview(guild_id):
    """获取服务器的基本信息预览"""
    # 处理 CORS 预检请求
    if request.method == "OPTIONS":
        return jsonify({}), 200

    if not hasattr(current_app, "bot"):
        return jsonify({"success": False, "error": "Bot 未连接"}), 503

    try:
        guild = current_app.bot.get_guild(int(guild_id))
        if not guild:
            return jsonify({"success": False, "error": "未找到该服务器"}), 404

        # 在线人数
        online = sum(1 for m in guild.members
                     if m.status != discord.Status.offline)

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
    """获取服务器的文字频道列表"""
    # 处理 CORS 预检请求
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


# ==================== 发送消息 ====================

@app.route("/api/send-message", methods=["POST", "OPTIONS"])
async def api_send_message():
    """通过机器人向指定频道发送消息"""
    # 处理 CORS 预检请求
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
            return jsonify({"success": False, "error": "缺少 content（消息内容）"}), 400

        if len(content) > 2000:
            return jsonify({"success": False, "error": "消息内容超过 2000 字符限制"}), 400

        channel = current_app.bot.get_channel(int(channel_id))
        if not channel:
            return jsonify({"success": False, "error": "未找到该频道"}), 404

        # 检查权限
        perms = channel.permissions_for(channel.guild.me)
        if not perms.send_messages:
            return jsonify({"success": False, "error": "机器人无发送消息权限"}), 403

        # 构建 embed
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
                    pass  # 缩略图 URL 无效时忽略

            # 验证 embed 总长度
            total_len = len(embed_data.get("title", "")) + \
                        len(embed_data.get("description", "")) + \
                        len(embed_data.get("footer", ""))
            if total_len > 6000:
                return jsonify({"success": False, "error": "Embed 总内容超过 6000 字符限制"}), 400

        # 发送消息
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
        return jsonify({"success": False, "error": "机器人权限不足，无法发送消息"}), 403
    except discord.HTTPException as e:
        logger.error(f"Discord HTTP 错误: {e}")
        return jsonify({"success": False, "error": f"Discord API 错误: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 服务器设置 ====================

@app.route("/api/settings/<guild_id>", methods=["GET", "POST", "OPTIONS"])
async def api_settings(guild_id):
    # 处理 CORS 预检请求
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


# ==================== 健康检查 ====================

@app.route("/api/health", methods=["GET", "OPTIONS"])
async def api_health():
    # 处理 CORS 预检请求
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
