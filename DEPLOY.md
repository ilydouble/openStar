# iCore 服务器部署指南

## 📋 前置要求

服务器需要安装以下工具：

- **Python 3.11+**
- **Node.js 18+** (推荐 20.x)
- **Git**
- **pip** (Python 包管理器)
- **npm** (Node.js 包管理器)

---

## 🚀 首次部署

### 1. 登录服务器

```bash
ssh user@your-server-ip
```

### 2. 下载并运行部署脚本

```bash
# 下载部署脚本（或手动上传 deploy.sh）
wget https://raw.githubusercontent.com/ilydouble/openStar/main/deploy.sh
chmod +x deploy.sh

# 首次运行会自动克隆代码
./deploy.sh
```

### 3. 配置环境变量

部署脚本会检测 `.env` 文件是否存在，如果不存在会提示你创建：

```bash
cd ~/icore/icore-agent
cp .env.example .env
nano .env  # 或用 vim 编辑
```

**必须配置的字段**：

```bash
# LLM API Keys（至少配置一个）
ZAI_API_KEY=your-zai-key              # 如果用 zai/glm-4.7
ANTHROPIC_API_KEY=your-anthropic-key  # 如果用 Claude

# 邮件服务（Resend）
RESEND_API_KEY=re_xxxxxxxxxxxx        # 从 resend.com 获取

# 数据持久化路径（生产环境必改）
CONTROL_PLANE_STORE_PATH=/var/lib/icore/control-plane.json
CHROMA_PATH=/var/lib/icore/chroma
IMAGE_SAVE_DIR=/var/lib/icore/images
```

### 4. 再次运行部署脚本

配置好 `.env` 后重新运行：

```bash
./deploy.sh
```

---

## 🔄 更新部署（拉取最新代码）

只需再次运行部署脚本，会自动：
1. 拉取最新代码 (`git pull`)
2. 停止旧服务
3. 安装新依赖
4. 重新构建前端
5. 启动新服务

```bash
cd ~
./deploy.sh
```

---

## 🛑 停止服务

```bash
./stop.sh
```

或手动停止：

```bash
pkill -f "uvicorn icore_agent.main:app"  # 停止后端
pkill -f "vite.*icore-agent-web"         # 停止前端
```

---

## 📊 查看日志

```bash
# 后端日志
tail -f ~/icore/icore-agent/logs/backend.log

# 前端日志
tail -f ~/icore/icore-agent-web/logs/frontend.log
```

---

## 🌐 访问服务

- **前端**: `http://YOUR_SERVER_IP:5173`
- **后端 API**: `http://YOUR_SERVER_IP:8080`
- **API 文档**: `http://YOUR_SERVER_IP:8080/docs` (DEBUG=true 时可用)

---

## 🔧 生产环境优化

### 1. 使用 Nginx 反向代理（推荐）

不要直接暴露 5173 和 8080 端口，用 Nginx 统一代理到 80/443：

```nginx
# /etc/nginx/sites-available/icore
server {
    listen 80;
    server_name icore.yourdomain.com;

    # 前端静态资源
    location / {
        root /root/icore/icore-agent-web/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

启用配置：

```bash
ln -s /etc/nginx/sites-available/icore /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

### 2. 使用 systemd 服务（开机自启）

创建后端服务：

```bash
sudo nano /etc/systemd/system/icore-backend.service
```

```ini
[Unit]
Description=iCore Backend API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/icore/icore-agent
ExecStart=/usr/bin/python3 -m uvicorn icore_agent.main:app --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable icore-backend
sudo systemctl start icore-backend
sudo systemctl status icore-backend
```

---

## ❓ 故障排查

### 后端启动失败

```bash
# 查看详细错误
tail -100 ~/icore/icore-agent/logs/backend.log

# 检查端口占用
lsof -i:8080

# 手动启动测试
cd ~/icore/icore-agent
uvicorn icore_agent.main:app --host 0.0.0.0 --port 8080
```

### 前端白屏

```bash
# 检查构建是否成功
ls -la ~/icore/icore-agent-web/dist/

# 重新构建
cd ~/icore/icore-agent-web
npm run build
```

### 验证码收不到

检查 `.env` 里的 `RESEND_API_KEY` 是否正确：

```bash
grep RESEND_API_KEY ~/icore/icore-agent/.env
```

---

## 📞 获取帮助

- GitHub Issues: https://github.com/ilydouble/openStar/issues
- 查看 API 文档: http://YOUR_SERVER_IP:8080/docs
