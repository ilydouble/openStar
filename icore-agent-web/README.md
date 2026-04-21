# iCore Agent Web Frontend

基于 Vue 3 和 Vite 的前端应用，提供现代化的用户界面和国际化支持。

## 功能特性

- 🎨 现代化 UI 设计
- 🌍 中文/英文双语支持
- 💬 实时流式聊天
- 📱 响应式设计
- ⚡ 快速开发体验

## 技术栈

- **Vue 3** - Composition API
- **Vite** - 快速构建
- **Vue Router** - 路由管理
- **Vue I18n** - 国际化
- **Tailwind CSS** - 样式框架
- **Marked** - Markdown 渲染

## 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

## 项目结构

```
src/
├── api/                # API 调用
├── components/         # 可复用组件
│   ├── AgentCard.vue
│   ├── ChatPanel.vue
│   ├── SearchBar.vue
│   └── ...
├── views/             # 页面组件
│   ├── HomeView.vue
│   └── ChatView.vue
├── locales/           # 国际化文件
│   ├── zh-CN.js
│   └── en-US.js
├── i18n/             # i18n 配置
├── style.css         # 全局样式
└── main.js          # 应用入口
```

## 国际化

### 添加新的翻译

编辑 `src/locales/zh-CN.js` 和 `src/locales/en-US.js`：

```javascript
// zh-CN.js
export default {
  newKey: '中文文本',
}

// en-US.js
export default {
  newKey: 'English text',
}
```

### 在组件中使用

```vue
<template>
  <div>{{ t('newKey') }}</div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>
```

## 环境变量

创建 `.env` 文件（开发环境）或 `.env.production`（生产环境）：

```bash
VITE_API_BASE_URL=http://localhost:8080
```

## 开发建议

- 使用 Vue DevTools 调试
- 遵循 Vue 3 Composition API 最佳实践
- 组件保持单一职责
- 合理使用 TypeScript（可选）
