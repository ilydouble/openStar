# iCore 智能工作台改造发现

## 代码结构

- 前端应用位于 `icore-agent-web`，使用 Vue 3、Vite、Tailwind 和 vue-i18n。
- 工作台主界面在 `icore-agent-web/src/views/HomeView.vue`。
- 现有能力入口来自 `home.shortcuts` 和 `home.templates` 国际化配置。
- 点击入口不会直接调用独立任务 API，而是设置 `activeShortcutId`，提交时通过 `composeScenarioPrompt` 将模板要求包进聊天消息。
- 后端 agent hint 目前由 `SHORTCUT_HINT` 映射到 `research`、`code`、`knowledge`、`image`、`data`、`chat`。

## 产品判断

- 现有架构适合先做“产品语义改造”：不改后端协议，先把通用能力包装成岗位任务。
- 风险最小的改法是保留内部 id 和 agent hint，仅替换外显文案、模板结构和首页按钮布局。
- AI 员工表达需要避免过度承诺，当前阶段更适合称为“AI 运营助理”或“岗位任务”。
- 首次引导选择函数原先引用了 `scenarios.value`，但 `HomeView.vue` 内没有该变量；改造时顺带修正为直接验证 shortcut id。
- 展示型任务卡信息密度过高，真实用户更适合“先选助理、再点任务、再补资料”的选择型入口。
