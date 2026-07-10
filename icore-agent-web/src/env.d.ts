/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_PROXY_TARGET?: string
  readonly VITE_PUBLIC_API_BASE_URL?: string
  readonly VITE_API_TIMEOUT_MS?: string
  readonly VITE_FILE_TIMEOUT_MS?: string
  readonly VITE_API_RETRY_COUNT?: string
  readonly VITE_DEBUG_AUTH?: string
  readonly VITE_DEBUG_HTTP?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
