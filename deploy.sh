#!/bin/bash
set -e  # 遇到错误立即退出

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# iCore 服务器部署脚本
# 功能：拉取最新代码 → 构建前端 → 重启前后端
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

# ── 1. 拉取最新代码 ───────────────────────────────────
log_info "拉取最新代码..."
git pull origin main
log_success "代码已更新"

# ── 2. 检查 .env 文件（仅警告） ───────────────────────
if [ ! -f "icore-agent/.env" ]; then
    log_warn ".env 文件不存在，后端可能无法启动"
    log_warn "建议：cp icore-agent/.env.example icore-agent/.env"
fi

# ── 3. 停止旧服务 ─────────────────────────────────────
log_info "停止旧服务..."
pkill -f "uvicorn icore_agent.main:app" || log_warn "后端未运行"
pkill -f "vite.*icore-agent-web" || log_warn "前端未运行"
sleep 2

# ── 4. 构建前端（如果有变化） ─────────────────────────
log_info "构建前端..."
cd icore-agent-web
npm run build
log_success "前端构建完成 → dist/"

# ── 5. 启动后端服务 (后台运行) ───────────────────────
log_info "启动后端服务 (端口 8080)..."
cd ../icore-agent
mkdir -p logs
# 必须从 src/ 父目录启动，或者用 python -m 模式
nohup python -m uvicorn icore_agent.main:app \
    --host 0.0.0.0 \
    --port 8080 \
    --app-dir src \
    > logs/backend.log 2>&1 &
BACKEND_PID=$!
log_success "后端已启动 (PID: $BACKEND_PID)"

# ── 6. 启动前端服务 (开发模式) ───────────────────────
log_info "启动前端开发服务器 (端口 5173)..."
cd ../icore-agent-web
mkdir -p logs
nohup npm run dev -- --host 0.0.0.0 \
    > logs/frontend.log 2>&1 &
FRONTEND_PID=$!
log_success "前端已启动 (PID: $FRONTEND_PID)"

# ── 7. 等待服务就绪 ───────────────────────────────────
log_info "等待服务启动..."
sleep 5

# 检查后端健康
if curl -sf http://localhost:8080/api/v1/health > /dev/null 2>&1; then
    log_success "✅ 后端服务正常"
else
    log_warn "⚠️  后端可能未就绪，查看日志: tail -f icore-agent/logs/backend.log"
fi

# 检查前端健康
if curl -sf http://localhost:5173 > /dev/null 2>&1; then
    log_success "✅ 前端服务正常"
else
    log_warn "⚠️  前端可能未就绪，查看日志: tail -f icore-agent-web/logs/frontend.log"
fi

# ── 8. 输出访问信息 ───────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_success "🚀 iCore 部署完成！"
echo ""
echo "  📌 前端: http://YOUR_SERVER_IP:5173"
echo "  📌 后端: http://YOUR_SERVER_IP:8080"
echo ""
echo "  📊 查看日志:"
echo "     tail -f icore-agent/logs/backend.log"
echo "     tail -f icore-agent-web/logs/frontend.log"
echo ""
echo "  🛑 停止服务: ./stop.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
