import { getBrowserStorage, readStoredString, removeStoredKey, writeStoredString } from '../stores/browserStorage.js'
import { authTrace, isAuthTracingEnabled } from './trace.js'

const TOKEN_KEY = 'icore_access_token'
const USER_KEY = 'icore_current_user'

/** Same-tab bearer mirror when persisted storage is unreadable or rejects writes (privacy / quota). */
let volatileAccessToken = ''

export function getAccessToken() {
  try {
    const persisted = readStoredString(getBrowserStorage(), TOKEN_KEY, '')
    if (typeof persisted === 'string' && persisted.length > 0) {
      if (persisted !== volatileAccessToken) {
        volatileAccessToken = persisted
      }
      return persisted
    }
  } catch {
    /* fall through */
  }
  return typeof volatileAccessToken === 'string' ? volatileAccessToken : ''
}

export function setSession(accessToken, user = null) {
  authTrace('setSession(before-write)', {
    accessTokenTruthy: Boolean(accessToken),
    accessTokenLength: typeof accessToken === 'string' ? accessToken.length : 0,
    hasUser: Boolean(user),
  })

  const storage = getBrowserStorage()
  authTrace('setSession(storage)', { storageWritable: Boolean(storage) })

  if (typeof accessToken === 'string' && accessToken.length > 0) {
    volatileAccessToken = accessToken
    writeStoredString(storage, TOKEN_KEY, accessToken)
  } else {
    volatileAccessToken = ''
    removeStoredKey(storage, TOKEN_KEY)
  }
  if (user) {
    writeStoredString(storage, USER_KEY, JSON.stringify(user))
  } else {
    removeStoredKey(storage, USER_KEY)
  }

  if (isAuthTracingEnabled() && accessToken && storage) {
    const readBack = storage.getItem(TOKEN_KEY)
    authTrace('setSession(read-back-verify)', {
      key: TOKEN_KEY,
      matches: readBack === accessToken,
      readBackLength: readBack?.length ?? 0,
    })
    const viaGetter = readStoredString(getBrowserStorage(), TOKEN_KEY, '')
    authTrace('setSession(read-back via readStoredString)', {
      matches: viaGetter === accessToken,
      length: viaGetter.length,
    })
  }
}

export function clearSession() {
  volatileAccessToken = ''
  const storage = getBrowserStorage()
  removeStoredKey(storage, TOKEN_KEY)
  removeStoredKey(storage, USER_KEY)
}

export function getStoredUser() {
  const raw = readStoredString(getBrowserStorage(), USER_KEY, '')
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function isAuthenticated() {
  return Boolean(getAccessToken())
}

/**
 * Snapshot current token presence/length without logging the secret.
 * Called after login/register to verify storage + getters (when tracing enabled).
 */
export function peekAccessTokenState(label = 'peekAccessTokenState') {
  const storage = getBrowserStorage()
  const rawDirect = storage?.getItem(TOKEN_KEY) ?? ''
  const viaReader = readStoredString(storage, TOKEN_KEY, '')
  authTrace(label, {
    tokenPresent: Boolean(viaReader) || Boolean(volatileAccessToken),
    tokenLength: viaReader.length || volatileAccessToken.length,
    volatileTokenLength: volatileAccessToken.length,
    rawMatchesReader: rawDirect === viaReader,
    rawLen: rawDirect.length,
  })
}

export function buildAuthHeaders(extra = {}, tokenReader = getAccessToken) {
  const token = tokenReader()
  return token
    ? {
        ...extra,
        Authorization: `Bearer ${token}`,
      }
    : extra
}
