export default {
  common: {
    platform: '平台',
  },
  navbar: {
    title: '星纬智能AI',
    admin: '管理员',
  },
  home: {
    title: 'iCore 智能代理平台',
    subtitle: '企业级智能能力，快速响应、专注结果，随时就绪。',
    description: '为您的业务提供高效、安全、可控的企业级 AI 服务。',
    startChat: '开始对话',
    heroTitle: 'iCore 智能工作台',
    greeting: '今天想做什么？',
    inputPlaceholder: '随便问，或让我帮你创作…',
    chatInput: {
      addFileOrPhoto: '添加文件或图片',
      createImage: '生成图片',
      thinkDeeply: '深度思考',
      searchInternet: '联网搜索',
      selectAgent: '选择智能体',
    },
    signIn: '登录',
    signUp: '注册',
    sidebar: {
      new: '新建',
      home: '首页',
      chat: '对话',
      flow: '流程',
      more: '更多',
      language: '语言',
    },
    shortcuts: [
      {
        id: 'research',
        label: '研究',
        prompt: '请就我所在行业的一个新兴趋势写一份精炼的研究要点，并列出 5 个延伸阅读来源。',
      },
      {
        id: 'code',
        label: '代码',
        prompt: '帮我写一个小而清晰的函数，补充注释，并说明边界情况与简单测试思路。',
      },
      {
        id: 'docs',
        label: '文档',
        prompt: '把这些要点整理成一页内部文档：标题层级 + 执行摘要。',
      },
      {
        id: 'chat',
        label: '问答',
        prompt: '我们来做聚焦问答：每次只问我一个澄清问题。',
      },
      {
        id: 'image',
        label: '视觉',
        prompt: '描述一幅图像概念：主体、光线、镜头感、配色与情绪。',
      },
      {
        id: 'data',
        label: '数据',
        prompt: '为小型分析看板给出一个最小数据模型示例 SQL。',
      },
    ],
    suggestions: [
      { label: '总结长文档', prompt: '如何把一份长文档清晰总结给管理层阅读？请给出结构建议。' },
      { label: '写一封邮件', prompt: '帮我写一封简洁专业的会议跟进邮件。' },
      { label: '解释概念', prompt: '用通俗语言解释 REST API，并给一个简短例子。' },
      { label: '项目规划', prompt: '为一个两周 MVP 列出最小可行的里程碑计划。' },
    ],
    features: {
      research: '深度研究',
      code: '代码助手',
      knowledge: '知识库',
    },
    researchDesc: '多源信息合成与竞争分析',
    codeDesc: '编写、调试和执行代码，多步骤任务执行',
    knowledgeDesc: '通过 RAG 查询内部知识库',
  },
  chat: {
    placeholder: '请输入您的问题...',
    send: '发送',
    thinking: '思考中...',
  },
  theme: {
    switchToLight: '切换到浅色模式',
    switchToDark: '切换到深色模式',
  },
}
