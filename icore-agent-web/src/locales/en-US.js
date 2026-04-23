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
        prompt:
          'Give me a tight research brief on one emerging topic in my industry, with 5 sources to read next.',
      },
      {
        id: 'code',
        label: 'Code',
        prompt: 'Help me write a small, well-documented function and include edge cases and tests.',
      },
      {
        id: 'docs',
        label: 'Docs',
        prompt: 'Turn rough bullet notes into a crisp one-pager with headings and a short executive summary.',
      },
      {
        id: 'chat',
        label: 'Chat',
        prompt: 'Let’s do a focused Q&A — ask one clarifying question at a time.',
      },
      {
        id: 'image',
        label: 'Visual',
        prompt: 'Describe a detailed scene for an image concept: subject, lighting, lens, palette, and mood.',
      },
      {
        id: 'data',
        label: 'Data',
        prompt: 'Propose a minimal data model and example SQL for a small analytics dashboard.',
      },
    ],
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
  },
  theme: {
    switchToLight: 'Switch to light mode',
    switchToDark: 'Switch to dark mode',
  },
}
