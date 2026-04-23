export default {
  common: {
    platform: 'Platform',
  },
  navbar: {
    title: 'Star Wei AI',
    admin: 'Administrator',
  },
  home: {
    title: 'iCore Agent Platform',
    subtitle: 'Enterprise-grade intelligence — fast, focused, and ready when you are.',
    description: 'Provide efficient, secure and controllable enterprise-level AI services for your business.',
    startChat: 'Start Chat',
    heroTitle: 'iCore AI Workspace',
    greeting: 'What can I help you with?',
    inputPlaceholder: 'Ask anything, create anything…',
    chatInput: {
      addFileOrPhoto: 'Add file or photo',
      createImage: 'Create image',
      thinkDeeply: 'Think deeply',
      searchInternet: 'Search the internet',
      selectAgent: 'Select Agent',
    },
    signIn: 'Sign in',
    signUp: 'Sign up',
    sidebar: {
      new: 'New',
      home: 'Home',
      chat: 'Chat',
      flow: 'Flow',
      more: 'More',
      language: 'Language',
    },
    shortcuts: [
      {
        id: 'research',
        label: 'Research',
        placeholder: 'What would you like to research? I\u2019ll search the web and cross-check sources.',
      },
      {
        id: 'code',
        label: 'Code',
        placeholder: 'Describe the feature to build or the bug to debug\u2026',
      },
      {
        id: 'docs',
        label: 'Docs',
        placeholder: 'Ask about your knowledge base, or what should I organize? (upload docs first)',
      },
      {
        id: 'chat',
        label: 'Chat',
        placeholder: 'Ask me anything \u2014 focused chat, no tools.',
      },
      {
        id: 'image',
        label: 'Visual',
        placeholder: 'Describe the image to generate, or upload one to analyze\u2026',
      },
      {
        id: 'data',
        label: 'Data',
        placeholder: 'What\u2019s your data and what would you like to learn? (upload CSV / Excel)',
      },
    ],
    modePill: {
      suffix: ' mode',
      clear: 'Exit mode',
    },
    suggestions: [
      { label: 'Summarize a long document', prompt: 'How should I summarize a long document clearly for executives?' },
      { label: 'Draft an email', prompt: 'Help me draft a concise professional email to follow up after a meeting.' },
      { label: 'Explain a concept', prompt: 'Explain REST APIs in simple terms with a short example.' },
      { label: 'Plan a project', prompt: 'Outline a minimal project plan with milestones for a 2-week MVP.' },
    ],
    features: {
      research: 'Deep Research',
      code: 'Code Assistant',
      knowledge: 'Knowledge Base',
    },
    researchDesc: 'Multi-source information synthesis and competitive analysis',
    codeDesc: 'Write, debug and execute code, multi-step task execution',
    knowledgeDesc: 'Query internal knowledge base via RAG',
  },
  chat: {
    placeholder: 'Enter your question...',
    send: 'Send',
    thinking: 'Thinking...',
    attachFile: 'Attach file (PDF / DOCX / TXT / MD)',
    stepsLive: 'Running ({n} step(s))',
    stepsCollapsed: 'Thinking process ({n} step(s))',
  },
  theme: {
    switchToLight: 'Switch to light mode',
    switchToDark: 'Switch to dark mode',
  },
}
