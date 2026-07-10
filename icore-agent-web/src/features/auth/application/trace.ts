/**
 * Structured auth/token tracing for debugging (login → storage → outbound headers).
 * Enable with dev server defaults, or set VITE_DEBUG_AUTH=true for production debugging.
 */

export function isAuthTracingEnabled(): boolean {
  try {
    return (
      typeof import.meta !== 'undefined' &&
      import.meta.env &&
      (import.meta.env.DEV === true || import.meta.env.VITE_DEBUG_AUTH === 'true')
    )
  } catch {
    return false
  }
}

/**
 * Write auth diagnostic data when auth tracing is enabled.
 */
export function authTrace(tag: string, data: Record<string, unknown> | undefined = undefined): void {
  if (!isAuthTracingEnabled()) return
  const prefix = '[icore-auth]'
  if (data === undefined) {
    console.log(prefix, tag)
  } else {
    console.log(prefix, tag, data)
  }
}
