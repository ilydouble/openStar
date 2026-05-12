#!/bin/bash
set -e  # 遇到错误立即退出

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# iCore 服务器部署脚本
# 功能：拉取最新代码 → 安装依赖 → 构建前端 → 启动前后端
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROJECT_DIR="$HOME/icore"  # 项目根目录，首次运行会自动 clone
REPO_URL="https://github.com/ilydouble/openStar.git"

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ── 1. 克隆或拉取最新代码 ────────────────────────────
if [ ! -d "$PROJECT_DIR" ]; then
    log_info "首次部署，克隆仓库..."
    git clone "$REPO_URL" "$PROJECT_DIR"
    log_success "仓库克隆完成"
else
    log_info "拉取最新代码..."
    cd "$PROJECT_DIR"
    git fetch origin
    git reset --hard origin/main  # ⚠️ 强制覆盖本地修改
    log_success "代码更新完成"
fi

cd "$PROJECT_DIR"

# ── 2. 检查 .env 文件 ─────────────────────────────────
if [ ! -f "$PROJECT_DIR/icore-agent/.env" ]; then
    log_error ".env 文件不存在，请先配置："
    echo "  cp icore-agent/.env.example icore-agent/.env"
    echo "  然后编辑 icore-agent/.env 填入你的 API Keys"
    exit 1
fi

# ── 3. 停止旧服务 ─────────────────────────────────────
log_info "停止旧服务..."
pkill -f "uvicorn icore_agent.main:app" || log_warn "后端未运行"
pkill -f "vite.*icore-agent-web" || log_warn "前端未运行"
sleep 2

# ── 4. 安装后端依赖 ───────────────────────────────────
log_info "安装后端依赖 (Python)..."
cd "$PROJECT_DIR/icore-agent"
pip install -r requirements.txt -q
log_success "后端依赖安装完成"

# ── 5. 安装前端依赖 ───────────────────────────────────
log_info "安装前端依赖 (Node.js)..."
cd "$PROJECT_DIR/icore-agent-web"
npm install --silent
log_success "前端依赖安装完成"

# ── 6. 构建前端静态资源 ──────────────────────────────
log_info "构建前端生产版本..."
npm run build
log_success "前端构建完成 → dist/"

# ── 7. 启动后端服务 (后台运行) ───────────────────────
log_info "启动后端服务 (端口 8080)..."
cd "$PROJECT_DIR/icore-agent"
nohup uvicorn icore_agent.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    > logs/backend.log 2>&1 &
BACKEND_PID=$!
log_success "后端已启动 (PID: $BACKEND_PID)"

# ── 8. 启动前端服务 (开发模式，生产用 Nginx) ────────
log_info "启动前端开发服务器 (端口 5173)..."
cd "$PROJECT_DIR/icore-agent-web"
nohup npm run dev -- --host 0.0.0.0 \
    > logs/frontend.log 2>&1 &
FRONTEND_PID=$!
log_success "前端已启动 (PID: $FRONTEND_PID)"

# ── 9. 等待服务就绪 ───────────────────────────────────
log_info "等待服务启动..."
sleep 5

# 检查后端健康
if curl -sf http://localhost:8080/api/v1/health > /dev/null; then
    log_success "✅ 后端服务正常 (http://localhost:8080)"
else
    log_error "❌ 后端启动失败，查看日志: tail -f $PROJECT_DIR/icore-agent/logs/backend.log"
    exit 1
fi

# 检查前端健康
if curl -sf http://localhost:5173 > /dev/null; then
    log_success "✅ 前端服务正常 (http://localhost:5173)"
else
    log_warn "⚠️  前端可能未就绪，查看日志: tail -f $PROJECT_DIR/icore-agent-web/logs/frontend.log"
fi

# ── 10. 输出访问信息 ──────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_success "🚀 iCore 部署完成！"
echo ""
echo "  📌 前端访问地址: http://YOUR_SERVER_IP:5173"
echo "  📌 后端 API:     http://YOUR_SERVER_IP:8080"
echo ""
echo "  📊 查看日志:"
echo "     后端: tail -f $PROJECT_DIR/icore-agent/logs/backend.log"
echo "     前端: tail -f $PROJECT_DIR/icore-agent-web/logs/frontend.log"
echo ""
echo "  🛑 停止服务:"
echo "     kill $BACKEND_PID $FRONTEND_PID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
