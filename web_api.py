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
