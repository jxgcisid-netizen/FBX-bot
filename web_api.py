<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FBX Bot - 控制面板</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>

    <!-- 锁屏 -->
    <div class="lockscreen" id="lockscreen">
        <div class="lock-box">
            <div class="lock-icon">🔐</div>
            <div class="lock-title">FBX<span>Bot</span> 控制面板</div>
            <div class="lock-subtitle">请输入访问密码</div>
            <input type="password" class="lock-input" id="password-input"
                   placeholder="••••••" autocomplete="current-password" maxlength="64"
                   onkeydown="if(event.key==='Enter')Auth.unlock()">
            <button class="lock-btn" id="lock-btn" onclick="Auth.unlock()">🔓 解锁</button>
            <label class="lock-remember">
                <input type="checkbox" id="remember-checkbox" checked>
                记住我（下次自动登录）
            </label>
            <div class="lock-error" id="lock-error"></div>
        </div>
    </div>

    <!-- 选择服务器弹窗 -->
    <div class="lockscreen" id="guild-picker" style="display:none;">
        <div class="lock-box" style="padding:36px 32px;text-align:left;">
            <div style="font-size:18px;font-weight:700;margin-bottom:6px;">🌐 选择服务器</div>
            <div style="font-size:12px;color:var(--text-muted);margin-bottom:20px;">请选择要管理的 Discord 服务器</div>
            <div id="guild-picker-list" style="max-height:300px;overflow-y:auto;"></div>
        </div>
    </div>

    <!-- 导航栏 -->
    <nav class="navbar">
        <div class="navbar-brand">FBX<span>Bot</span></div>
        <div class="navbar-actions">
            <div class="navbar-status">
                <div class="status-dot" id="dot"></div>
                <span id="status-text">连接中...</span>
            </div>
            <select id="global-guild-select" onchange="onGlobalGuildChange()"
                style="background:var(--surface);border:1px solid var(--border);color:var(--cyan);padding:5px 10px;border-radius:var(--radius-xs);font-size:12px;max-width:200px;font-weight:600;">
                <option value="">加载中...</option>
            </select>
            <button class="btn-icon danger" id="btn-toggle-bot" onclick="BotControl.toggle()">⏹ 停止</button>
            <button class="btn-icon" onclick="Auth.lock()">🔒</button>
        </div>
    </nav>

    <!-- 主内容 -->
    <div class="container" id="main-content">
        <div class="tabs">
            <button class="tab active" onclick="UI.switchTab('dashboard')">📊 仪表盘</button>
            <button class="tab" onclick="UI.switchTab('messenger')">💬 消息发送</button>
            <button class="tab" onclick="UI.switchTab('settings')">⚙️ 设置</button>
        </div>

        <!-- 仪表盘 -->
        <div class="tab-content active" id="tab-dashboard">
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-label">📊 总用户</div><div class="stat-value" id="total-users">--</div></div>
                <div class="stat-card"><div class="stat-label">🌐 服务器</div><div class="stat-value" id="total-guilds">--</div></div>
                <div class="stat-card"><div class="stat-label">🏆 最高等级</div><div class="stat-value" id="max-level">--</div></div>
                <div class="stat-card"><div class="stat-label">💚 Bot 状态</div><div class="stat-value" style="font-size:16px;" id="bot-status">在线</div></div>
            </div>
            <div class="content-grid">
                <div class="panel">
                    <div class="panel-header">服务器列表<span class="badge" id="guild-count">0</span></div>
                    <div class="panel-body" id="guilds-panel"><div class="spinner"></div></div>
                </div>
                <div class="panel">
                    <div class="panel-header">排行榜</div>
                    <div class="panel-body" id="lb-content">
                        <div class="empty-state"><div class="icon">📋</div>选择服务器后自动加载</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 消息发送 -->
        <div class="tab-content" id="tab-messenger">
            <div class="content-grid single">
                <div class="panel full">
                    <div class="panel-header">
                        💬 通过 Bot 发送消息
                        <select id="msg-channel-select"
                            style="background:var(--bg);border:1px solid var(--border);color:var(--text);padding:5px 8px;border-radius:var(--radius-xs);font-size:11px;">
                            <option value="">选择频道</option>
                        </select>
                    </div>
                    <div class="panel-body">
                        <div class="guild-preview" id="guild-preview" style="display:none;"></div>
                        <div style="position:relative;">
                            <textarea id="message-content"
                                      placeholder="输入消息... @everyone @here"
                                      maxlength="2000"
                                      oninput="Messenger.onInput()"
                                      onkeydown="Messenger.onKeydown(event)"></textarea>
                            <div class="mention-suggestions" id="mention-suggestions"></div>
                        </div>
                        <div class="char-count" id="char-count">0 / 2000</div>

                        <div class="file-upload-area" id="file-upload-area">
                            <div onclick="document.getElementById('file-input').click()" style="cursor:pointer;">
                                📎 点击上传文件/图片（或拖拽到此处）<br><span style="font-size:10px;">最大 8MB</span>
                            </div>
                            <input type="file" id="file-input" multiple style="display:none;"
                                   onchange="Messenger.handleFiles(this.files)"
                                   accept="image/*,.png,.jpg,.gif,.webp,.txt,.pdf,.mp4,.mp3,.zip">
                        </div>
                        <div class="file-list" id="file-list"></div>

                        <div class="toggle-row">
                            <label class="toggle">
                                <input type="checkbox" id="embed-enabled" onchange="Messenger.toggleEmbed()">
                                <span class="toggle-slider"></span>
                            </label>
                            <span style="font-size:12px;color:var(--text-secondary);">附加 Embed</span>
                        </div>
                        <div class="embed-options" id="embed-options" style="display:none;">
                            <div><label>标题</label><input type="text" id="embed-title" placeholder="Embed 标题" maxlength="256"></div>
                            <div><label>颜色</label><input type="text" id="embed-color" placeholder="#00b4d8" value="#00b4d8" maxlength="7"></div>
                            <div style="grid-column:1/-1;"><label>描述</label><input type="text" id="embed-description" placeholder="描述" maxlength="4096"></div>
                            <div><label>页脚</label><input type="text" id="embed-footer" placeholder="页脚" maxlength="2048"></div>
                            <div><label>缩略图 URL</label><input type="text" id="embed-thumbnail" placeholder="https://..."></div>
                        </div>

                        <div style="display:flex;gap:8px;margin-top:14px;">
                            <button class="btn btn-success" onclick="Messenger.send()" id="send-btn">📨 发送</button>
                            <button class="btn btn-outline" onclick="Messenger.preview()">👁 预览</button>
                        </div>
                        <div class="message-preview" id="message-preview">
                            <div style="font-size:10px;color:var(--text-muted);margin-bottom:6px;">预览</div>
                            <div id="preview-content" style="font-size:13px;white-space:pre-wrap;"></div>
                            <div class="preview-embed" id="preview-embed" style="display:none;">
                                <div class="preview-embed-title" id="preview-embed-title"></div>
                                <div class="preview-embed-desc" id="preview-embed-desc"></div>
                                <div class="preview-embed-footer" id="preview-embed-footer"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 设置 -->
        <div class="tab-content" id="tab-settings">
            <div class="content-grid single">
                <div class="panel full">
                    <div class="panel-header">⚙️ 服务器设置</div>
                    <div class="panel-body" id="settings-panel">
                        <div class="empty-state"><div class="icon">🔒</div>选择服务器后自动加载</div>
                    </div>
                </div>
                <div class="panel full">
                    <div class="panel-header">🛡️ 成员管理</div>
                    <div class="panel-body" id="mod-panel">
                        <div class="empty-state"><div class="icon">🛡️</div>选择服务器后自动加载</div>
                    </div>
                </div>
                <div class="panel full">
                    <div class="panel-header">⚠️ 危险区域</div>
                    <div class="panel-body">
                        <div class="danger-zone">
                            <div class="danger-zone-title" id="danger-title">⏹ 停止 Bot</div>
                            <p style="font-size:11px;color:var(--text-muted);margin-bottom:10px;" id="danger-desc">这将断开 Bot 与 Discord 的连接。</p>
                            <button class="btn btn-danger btn-sm" id="danger-btn" onclick="BotControl.toggle()">停止 Bot</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="toast-container" id="toast-container"></div>

<script>
// ====================================================================
// 全局
// ====================================================================
const API = "https://web--arcane--d9n9n2zg4zh5.code.run";
const SKEY = "fbxbot_auth_token";
const RKEY = "fbxbot_remember";

let guildList = [];
let activeGuild = null;
let botOnline = true;

async function api(url, opts = {}) {
    const t = localStorage.getItem(SKEY);
    const h = { ...(opts.headers || {}) };
    if (t) h["Authorization"] = "Bearer " + t;
    if (opts.body && typeof opts.body === "string" && !h["Content-Type"])
        h["Content-Type"] = "application/json";
    return fetch(url, { ...opts, headers: h });
}

function toast(msg, type) {
    const c = document.getElementById("toast-container");
    const d = document.createElement("div");
    d.className = "toast " + type; d.textContent = msg;
    c.appendChild(d);
    setTimeout(() => { d.style.opacity = "0"; d.style.transition = "opacity 0.3s"; setTimeout(() => d.remove(), 300); }, 3000);
}

function esc(s) {
    if (!s) return "";
    const d = document.createElement("div"); d.textContent = s; return d.innerHTML;
}

function animate(id, target) {
    const el = document.getElementById(id);
    const cur = parseInt(el.textContent.replace(/,/g, "")) || 0;
    if (cur === target) { el.textContent = target.toLocaleString(); return; }
    const dur = 600, start = performance.now();
    function upd(now) {
        const p = Math.min((now - start) / dur, 1);
        el.textContent = Math.round(cur + (target - cur) * (1 - Math.pow(1 - p, 3))).toLocaleString();
        if (p < 1) requestAnimationFrame(upd);
    }
    requestAnimationFrame(upd);
}

// ====================================================================
// 认证
// ====================================================================
const Auth = {
    async init() {
        document.getElementById("lockscreen").classList.remove("hidden");
        document.getElementById("password-input").focus();
        const r = localStorage.getItem(RKEY), t = localStorage.getItem(SKEY);
        if (r === "true" && t) {
            document.getElementById("password-input").disabled = true;
            document.getElementById("password-input").placeholder = "自动登录中...";
            document.getElementById("lock-btn").disabled = true;
            document.getElementById("lock-btn").textContent = "⏳ 验证中...";
            const ok = await this.verify(t);
            if (ok) { document.getElementById("lockscreen").classList.add("hidden"); App.init(); return; }
            localStorage.removeItem(SKEY);
            document.getElementById("password-input").disabled = false;
            document.getElementById("password-input").placeholder = "••••••";
            document.getElementById("password-input").value = "";
            document.getElementById("lock-btn").disabled = false;
            document.getElementById("lock-btn").textContent = "🔓 解锁";
            document.getElementById("lock-error").textContent = "登录已过期，请重新输入密码";
            document.getElementById("password-input").focus();
        }
    },
    async verify(t) {
        try { return (await (await api(API+"/api/verify-token",{headers:{Authorization:"Bearer "+t}})).json()).success===true; }
        catch(e){return false;}
    },
    async unlock() {
        const pw = document.getElementById("password-input").value.trim();
        const err = document.getElementById("lock-error");
        const btn = document.getElementById("lock-btn");
        const rem = document.getElementById("remember-checkbox").checked;
        if (!pw) { err.textContent = "请输入密码"; return; }
        btn.disabled = true; btn.textContent = "验证中..."; err.textContent = "";
        try {
            const r = await fetch(API+"/api/auth",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:pw})});
            const d = await r.json();
            if (d.success) {
                document.getElementById("lockscreen").classList.add("hidden");
                localStorage.setItem(SKEY, d.token);
                if (rem) localStorage.setItem(RKEY, "true"); else localStorage.removeItem(RKEY);
                App.init();
            } else {
                err.textContent = d.error || "密码错误";
                document.getElementById("password-input").value = "";
                document.getElementById("password-input").focus();
            }
        } catch (e) { err.textContent = "连接失败"; }
        finally { btn.disabled = false; btn.textContent = "🔓 解锁"; }
    },
    lock() {
        localStorage.removeItem(SKEY); localStorage.removeItem(RKEY);
        activeGuild = null;
        document.getElementById("lockscreen").classList.remove("hidden");
        document.getElementById("password-input").value = "";
        document.getElementById("password-input").disabled = false;
        document.getElementById("password-input").placeholder = "••••••";
        document.getElementById("lock-error").textContent = "";
        document.getElementById("lock-btn").disabled = false;
        document.getElementById("lock-btn").textContent = "🔓 解锁";
        document.getElementById("password-input").focus();
    }
};

// ====================================================================
// Bot 控制
// ====================================================================
const BotControl = {
    updateUI() {
        const btn = document.getElementById("btn-toggle-bot");
        const db = document.getElementById("danger-btn");
        const dt = document.getElementById("danger-title");
        const dd = document.getElementById("danger-desc");
        if (botOnline) {
            btn.textContent = "⏹ 停止"; btn.className = "btn-icon danger";
            if (db) { db.textContent = "停止 Bot"; db.className = "btn btn-danger btn-sm"; }
            if (dt) dt.textContent = "⏹ 停止 Bot";
            if (dd) dd.textContent = "这将断开 Bot 与 Discord 的连接。";
        } else {
            btn.textContent = "▶ 启动"; btn.className = "btn-icon success";
            if (db) { db.textContent = "启动 Bot"; db.className = "btn btn-success btn-sm"; }
            if (dt) dt.textContent = "▶ 启动 Bot";
            if (dd) dd.textContent = "Bot 当前离线，点击启动重新连接 Discord。";
        }
        const dot = document.getElementById("dot"), st = document.getElementById("status-text"),
              bs = document.getElementById("bot-status");
        if (botOnline) {
            dot.className = "status-dot online"; st.textContent = "已连接";
            bs.textContent = "在线"; bs.style.color = "var(--success)";
        } else {
            dot.className = "status-dot error"; st.textContent = "已停止";
            bs.textContent = "离线"; bs.style.color = "var(--danger)";
        }
    },
    async check() {
        try { const d = await (await api(API+"/api/bot-status")).json(); if (d.success) { botOnline = d.data.is_ready; this.updateUI(); } } catch(e) {}
    },
    async toggle() {
        if (botOnline) {
            if (!confirm("确定要停止 Bot 吗？")) return;
            try { const d = await (await api(API+"/api/stop-bot",{method:"POST"})).json(); if (d.success) { botOnline=false; this.updateUI(); toast("✅ Bot 已停止","success"); } else toast("❌ "+(d.error||"失败"),"error"); } catch(e) { toast("请求失败","error"); }
        } else {
            try {
                const d = await (await api(API+"/api/start-bot",{method:"POST"})).json();
                if (d.success) {
                    toast("🔄 Bot 正在启动...","info"); let cnt=0;
                    const iv=setInterval(async()=>{cnt++;try{const s=await(await api(API+"/api/bot-status")).json();if(s.success&&s.data.is_ready){clearInterval(iv);botOnline=true;this.updateUI();toast("✅ Bot 已重新上线","success");App.loadAll();}else if(cnt>=25){clearInterval(iv);toast("⚠️ 启动超时","error");}}catch(e){}},2000);
                } else toast("❌ "+(d.error||"失败"),"error");
            } catch(e) { toast("请求失败","error"); }
        }
    }
};

// ====================================================================
// UI
// ====================================================================
const UI = {
    switchTab(name) {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
        document.querySelector(`.tab[onclick="UI.switchTab('${name}')"]`).classList.add("active");
        document.getElementById("tab-" + name).classList.add("active");
        if (!activeGuild) return;
        if (name === "dashboard") Dashboard.load();
        if (name === "messenger") Messenger.onGuildReady();
        if (name === "settings") { Settings.load(); Moderation.load(); }
    }
};

// ====================================================================
// 全局选服务器
// ====================================================================
function showGuildPicker() {
    if (!guildList.length) return;
    const list = document.getElementById("guild-picker-list");
    list.innerHTML = guildList.map(g => `
        <div onclick="selectGlobalGuild('${g.guild_id}')" style="padding:12px;cursor:pointer;border-bottom:1px solid var(--border);transition:background 0.15s;"
             onmouseover="this.style.background='var(--cyan-glow)'" onmouseout="this.style.background=''">
            <div style="font-weight:600;">${esc(g.guild_name||'未知')}</div>
            <div style="font-size:11px;color:var(--text-muted);">${g.guild_id} · ${g.user_count} 用户</div>
        </div>
    `).join("");
    document.getElementById("guild-picker").style.display = "flex";
}

function selectGlobalGuild(gid) {
    activeGuild = guildList.find(g => g.guild_id === gid);
    document.getElementById("guild-picker").style.display = "none";
    document.getElementById("global-guild-select").value = gid;
    refreshAllPanels();
    toast("✅ " + (activeGuild?.guild_name || gid), "success");
}

function onGlobalGuildChange() {
    const gid = document.getElementById("global-guild-select").value;
    if (!gid) return;
    activeGuild = guildList.find(g => g.guild_id === gid);
    refreshAllPanels();
}

function refreshAllPanels() {
    if (!activeGuild) return;
    Dashboard.load();
    Messenger.onGuildReady();
    Settings.load();
    Moderation.load();
}

function fillGlobalSelect() {
    const sel = document.getElementById("global-guild-select");
    sel.innerHTML = '<option value="">选择服务器</option>';
    guildList.forEach(g => {
        const o = document.createElement("option");
        o.value = g.guild_id;
        o.textContent = (g.guild_name || "未知") + " (" + g.guild_id + ")";
        sel.appendChild(o);
    });
}

// ====================================================================
// 应用初始化
// ====================================================================
const App = {
    async init() {
        await BotControl.check();
        try { const d = await (await api(API+"/api/health")).json(); botOnline = d.success && d.bot_connected; } catch(e) { botOnline=false; }
        BotControl.updateUI();
        await this.loadAll();
        if (guildList.length > 0) showGuildPicker();
    },
    async loadAll() { await Promise.all([this.loadStats(), this.loadGuilds()]); },
    async loadStats() {
        try { const d = await (await api(API+"/api/stats")).json(); if (d.success) { animate("total-users",d.data.total_users); animate("total-guilds",d.data.total_guilds); animate("max-level",d.data.max_level); } } catch(e) {}
    },
    async loadGuilds() {
        const panel = document.getElementById("guilds-panel"); panel.innerHTML = '<div class="spinner"></div>';
        try {
            const d = await (await api(API+"/api/guilds")).json();
            if (d.success && d.data.length) {
                guildList = d.data;
                document.getElementById("guild-count").textContent = d.data.length;
                panel.innerHTML = `<table><thead><tr><th>服务器</th><th>用户</th><th>最高等级</th></tr></thead><tbody>
                    ${d.data.map(g => `<tr><td><div class="guild-name">${esc(g.guild_name||'未知')}</div><div class="guild-id">${g.guild_id}</div></td><td>${g.user_count.toLocaleString()}</td><td><span class="level-tag">Lv ${g.max_level}</span></td></tr>`).join("")}</tbody></table>`;
                fillGlobalSelect();
            } else panel.innerHTML = '<div class="empty-state"><div class="icon">📭</div>暂无数据</div>';
        } catch(e) { panel.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div>加载失败</div>'; }
    }
};

// ====================================================================
// 仪表盘
// ====================================================================
const Dashboard = {
    async load() {
        if (!activeGuild) return;
        const gid = activeGuild.guild_id;
        const lb = document.getElementById("lb-content"); lb.innerHTML = '<div class="spinner"></div>';
        try {
            const d = await (await api(API+"/api/leaderboard/"+gid)).json();
            if (d.success && d.data.length) {
                const icons = {1:"🥇",2:"🥈",3:"🥉"};
                lb.innerHTML = `<table><thead><tr><th>#</th><th>用户</th><th>等级</th><th>XP</th><th>语音XP</th></tr></thead><tbody>
                    ${d.data.map(r => `<tr><td><span class="rank-badge ${r.rank<=3?'rank-'+r.rank:'rank-other'}">${icons[r.rank]||r.rank}</span></td><td><span class="guild-name">${esc(r.user_name||'未知')}</span><div class="guild-id">${r.user_id}</div></td><td><span class="level-tag">Lv ${r.level}</span></td><td>${r.xp.toLocaleString()}</td><td style="color:var(--text-muted)">${r.voice_xp.toLocaleString()}</td></tr>`).join("")}</tbody></table>`;
            } else lb.innerHTML = '<div class="empty-state"><div class="icon">🔍</div>暂无数据</div>';
        } catch(e) { lb.innerHTML = '<div class="empty-state"><div class="icon">⚠️</div>加载失败</div>'; }
    }
};

// ====================================================================
// 消息发送
// ====================================================================
const Messenger = {
    mentionIndex: -1,
    files: [],

    async onGuildReady() {
        if (!activeGuild) return;
        const gid = activeGuild.guild_id;
        const cs = document.getElementById("msg-channel-select");
        const pv = document.getElementById("guild-preview");
        cs.innerHTML = '<option value="">加载中...</option>';

        try {
            const d = await (await api(API+"/api/guilds/"+gid+"/preview")).json();
            if (d.success) {
                const g = d.data;
                pv.style.display = "grid";
                pv.innerHTML = `<div class="guild-preview-item"><div class="val">${g.member_count}</div><div class="lbl">成员</div></div><div class="guild-preview-item"><div class="val">${g.online_count}</div><div class="lbl">在线</div></div><div class="guild-preview-item"><div class="val">${g.text_channels}</div><div class="lbl">文字频道</div></div><div class="guild-preview-item"><div class="val">${g.voice_channels}</div><div class="lbl">语音频道</div></div>`;
            }
        } catch(e) {}

        try {
            const d = await (await api(API+"/api/guilds/"+gid+"/channels")).json();
            if (d.success) {
                cs.innerHTML = '<option value="">选择频道</option>';
                d.data.forEach(ch => { const o = document.createElement("option"); o.value = ch.id; o.textContent = (ch.category?"["+ch.category+"] ":"")+"#"+ch.name; cs.appendChild(o); });
            } else cs.innerHTML = '<option value="">获取失败</option>';
        } catch(e) { cs.innerHTML = '<option value="">获取失败</option>'; }
    },

    onInput() {
        const ta = document.getElementById("message-content"), val = ta.value, cp = ta.selectionStart;
        const before = val.substring(0, cp), match = before.match(/@(\S*)$/);
        const sug = document.getElementById("mention-suggestions");
        if (!match) { sug.classList.remove("show"); this.mentionIndex = -1; this.updateCharCount(); return; }
        const q = match[1].toLowerCase();
        let items = [];
        if (q === "" || "everyone".startsWith(q)) items.push({id:"@everyone", name:"@everyone"});
        if (q === "" || "here".startsWith(q)) items.push({id:"@here", name:"@here"});
        if (items.length > 0) {
            this.mentionIndex = -1;
            sug.innerHTML = items.map((it,i) => `<div class="mention-item" data-idx="${i}" data-id="${it.id}" onmousedown="Messenger.insertMention(this)">${esc(it.name)}</div>`).join("");
            sug.classList.add("show");
        } else sug.classList.remove("show");
        this.updateCharCount();
    },

    onKeydown(e) {
        const sug = document.getElementById("mention-suggestions");
        if (!sug.classList.contains("show")) return;
        const items = sug.querySelectorAll(".mention-item");
        if (e.key==="ArrowDown"){e.preventDefault();this.mentionIndex=Math.min(this.mentionIndex+1,items.length-1);this._hl(items);}
        else if(e.key==="ArrowUp"){e.preventDefault();this.mentionIndex=Math.max(this.mentionIndex-1,0);this._hl(items);}
        else if(e.key==="Enter"&&this.mentionIndex>=0){e.preventDefault();this.insertMention(items[this.mentionIndex]);}
        else if(e.key==="Escape"){sug.classList.remove("show");this.mentionIndex=-1;}
    },

    _hl(items){items.forEach((it,i)=>it.style.background=i===this.mentionIndex?"var(--cyan-glow)":"");},

    insertMention(el){
        const ta=document.getElementById("message-content"),val=ta.value,cp=ta.selectionStart,before=val.substring(0,cp),after=val.substring(cp);
        ta.value=before.replace(/@\S*$/,"")+el.dataset.id+" "+after;
        document.getElementById("mention-suggestions").classList.remove("show");this.mentionIndex=-1;ta.focus();this.updateCharCount();
    },

    updateCharCount(){const l=document.getElementById("message-content").value.length,el=document.getElementById("char-count");el.textContent=l+" / 2000";el.className="char-count"+(l>1800?" warn":"")+(l>1950?" danger":"");},
    toggleEmbed(){document.getElementById("embed-options").style.display=document.getElementById("embed-enabled").checked?"grid":"none";},

    handleFiles(fl){for(const f of fl){if(f.size>8*1024*1024){toast(f.name+" 超过8MB","error");continue;}this.files.push(f);}this._rf();},
    _rf(){document.getElementById("file-list").innerHTML=this.files.map((f,i)=>`<div class="file-tag">📄 ${esc(f.name)} (${(f.size/1024).toFixed(1)}KB) <span class="remove" onclick="Messenger.removeFile(${i})">×</span></div>`).join("");},
    removeFile(i){this.files.splice(i,1);this._rf();},

    preview(){
        const c=document.getElementById("message-content").value;document.getElementById("message-preview").classList.add("show");
        document.getElementById("preview-content").textContent=c||"(空消息)";
        const pe=document.getElementById("preview-embed");
        if(document.getElementById("embed-enabled").checked){
            pe.style.display="block";pe.style.borderLeftColor=document.getElementById("embed-color").value||"#00b4d8";
            document.getElementById("preview-embed-title").textContent=document.getElementById("embed-title").value||"(无标题)";
            document.getElementById("preview-embed-desc").textContent=document.getElementById("embed-description").value||"(无描述)";
            document.getElementById("preview-embed-footer").textContent=document.getElementById("embed-footer").value||"";
        }else pe.style.display="none";
    },

    async send(){
        const cid = document.getElementById("msg-channel-select").value;
        const content = document.getElementById("message-content").value.trim();
        if (!cid) { toast("请选择频道", "error"); return; }
        if (!content && !this.files.length) { toast("请输入内容或上传文件", "error"); return; }
        const btn = document.getElementById("send-btn"); btn.disabled = true; btn.textContent = "发送中...";
        try {
            const token = localStorage.getItem(SKEY);
            const body = JSON.stringify({
                channel_id: cid,
                content: content,
                embed: document.getElementById("embed-enabled").checked ? {
                    enabled: true,
                    title: document.getElementById("embed-title").value,
                    description: document.getElementById("embed-description").value,
                    color: document.getElementById("embed-color").value,
                    footer: document.getElementById("embed-footer").value,
                    thumbnail_url: document.getElementById("embed-thumbnail").value
                } : { enabled: false }
            });
            const resp = await fetch(API+"/api/send-message", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + token
                },
                body: body
            });
            const d = await resp.json();
            if (d.success) {
                toast("✅ 已发送到 #" + d.data.channel_name, "success");
                document.getElementById("message-content").value = "";
                this.updateCharCount();
                this.files = []; this._rf();
                document.getElementById("message-preview").classList.remove("show");
            } else toast("❌ " + (d.error || "失败"), "error");
        } catch(e) { toast("发送失败", "error"); }
        finally { btn.disabled = false; btn.textContent = "📨 发送"; }
    }
};

// ====================================================================
// 设置
// ====================================================================
const Settings = {
    async load() {
        if (!activeGuild) return;
        const gid = activeGuild.guild_id, gn = activeGuild.guild_name;
        try {
            const d = await (await api(API+"/api/settings/"+gid)).json();
            if (d.success) {
                document.getElementById("settings-panel").innerHTML = `
                    <div style="margin-bottom:14px;font-size:12px;color:var(--text-secondary);">编辑: <strong style="color:var(--text);">${esc(gn)}</strong></div>
                    <div class="settings-row"><div><div class="settings-label">经验倍率</div><div class="settings-desc">消息 XP 倍率 (0.1-10.0)</div></div><div style="display:flex;align-items:center;gap:6px;"><input type="number" class="settings-input" id="setting-xp-rate" value="${d.data.xp_rate||1.0}" min="0.1" max="10.0" step="0.1"><span style="font-size:11px;color:var(--text-muted);">×</span></div></div>
                    <div class="settings-row"><div><div class="settings-label">语音经验倍率</div><div class="settings-desc">语音 XP 倍率 (0.1-10.0)</div></div><div style="display:flex;align-items:center;gap:6px;"><input type="number" class="settings-input" id="setting-voice-xp-rate" value="${d.data.voice_xp_rate||1.0}" min="0.1" max="10.0" step="0.1"><span style="font-size:11px;color:var(--text-muted);">×</span></div></div>
                    <button class="btn" onclick="Settings.save()" style="margin-top:14px;width:100%;">💾 保存</button>`;
            }
        } catch(e) {}
    },
    async save() {
        if (!activeGuild) return;
        const gid = activeGuild.guild_id;
        const xr = document.getElementById("setting-xp-rate")?.value;
        const vr = document.getElementById("setting-voice-xp-rate")?.value;
        try {
            const d = await (await api(API+"/api/settings/"+gid,{method:"POST",body:JSON.stringify({xp_rate:parseFloat(xr),voice_xp_rate:parseFloat(vr)})})).json();
            toast(d.success?"✅ 已保存":"❌ "+d.error,d.success?"success":"error");
        } catch(e) { toast("保存失败","error"); }
    }
};

// ====================================================================
// 成员管理
// ====================================================================
const Moderation = {
    async load() {
        if (!activeGuild) return;
        const gid = activeGuild.guild_id;
        try {
            const d = await (await api(API+"/api/guilds/"+gid+"/members")).json();
            if (d.success) {
                const list = d.data.members || d.data || [];
                const members = Array.isArray(list) ? list : [];
                document.getElementById("mod-panel").innerHTML = `
                    <div class="toolbar"><input type="text" id="mod-search" placeholder="搜索成员..." oninput="Moderation.filter()"></div>
                    <div style="max-height:350px;overflow-y:auto;">
                        <table><thead><tr><th>用户</th><th>ID</th><th>加入时间</th><th>操作</th></tr></thead>
                        <tbody id="mod-members-tbody">${members.map(m => `<tr data-name="${esc(m.display_name).toLowerCase()}" data-username="${esc(m.username||'').toLowerCase()}">
                            <td><div style="display:flex;align-items:center;gap:8px;"><img src="${m.avatar_url||''}" style="width:24px;height:24px;border-radius:50%;" onerror="this.style.display='none'"><span>${esc(m.display_name)}</span></div></td>
                            <td><span class="guild-id">${m.id}</span></td>
                            <td style="font-size:11px;color:var(--text-muted);">${m.joined_at?new Date(m.joined_at).toLocaleDateString():'-'}</td>
                            <td><button class="btn btn-danger btn-sm" onclick="Moderation.kick('${m.id}','${esc(m.display_name)}')">踢出</button> <button class="btn btn-danger btn-sm" onclick="Moderation.ban('${m.id}','${esc(m.display_name)}')">封禁</button></td>
                        </tr>`).join("")}</tbody></table>
                    </div>`;
            }
        } catch(e) {}
    },
    filter() {
        const q = (document.getElementById("mod-search")?.value||"").toLowerCase();
        document.querySelectorAll("#mod-members-tbody tr").forEach(tr => {
            const n = tr.dataset.name||"", u = tr.dataset.username||"";
            tr.style.display = n.includes(q)||u.includes(q) ? "" : "none";
        });
    },
    async kick(uid, name) {
        if (!confirm("确定要踢出 "+name+" 吗？")) return;
        if (!activeGuild) return;
        try {
            const d = await (await api(API+"/api/guilds/"+activeGuild.guild_id+"/kick",{method:"POST",body:JSON.stringify({user_id:uid,reason:"面板操作"})})).json();
            toast(d.success?"✅ 已踢出":"❌ "+(d.error||"失败"),d.success?"success":"error");
            if (d.success) this.load();
        } catch(e) { toast("请求失败","error"); }
    },
    async ban(uid, name) {
        if (!confirm("确定要封禁 "+name+" 吗？")) return;
        if (!activeGuild) return;
        try {
            const d = await (await api(API+"/api/guilds/"+activeGuild.guild_id+"/ban",{method:"POST",body:JSON.stringify({user_id:uid,reason:"面板操作",delete_days:1})})).json();
            toast(d.success?"✅ 已封禁":"❌ "+(d.error||"失败"),d.success?"success":"error");
            if (d.success) this.load();
        } catch(e) { toast("请求失败","error"); }
    }
};

// 拖拽上传
(function(){
    const a = document.getElementById("file-upload-area");
    a.addEventListener("dragover", e => { e.preventDefault(); a.classList.add("dragover"); });
    a.addEventListener("dragleave", () => a.classList.remove("dragover"));
    a.addEventListener("drop", e => { e.preventDefault(); a.classList.remove("dragover"); Messenger.handleFiles(e.dataTransfer.files); });
})();

Auth.init();
</script>
</body>
</html>
