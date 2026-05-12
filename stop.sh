#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# iCore 停止服务脚本
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}[STOP]${NC} 正在停止 iCore 服务..."

# 停止后端
if pkill -f "uvicorn icore_agent.main:app"; then
    echo -e "${GREEN}✓${NC} 后端已停止"
else
    echo -e "${YELLOW}!${NC} 后端未运行"
fi

# 停止前端
if pkill -f "vite.*icore-agent-web"; then
    echo -e "${GREEN}✓${NC} 前端已停止"
else
    echo -e "${YELLOW}!${NC} 前端未运行"
fi

echo -e "${GREEN}[DONE]${NC} 服务已全部停止"
