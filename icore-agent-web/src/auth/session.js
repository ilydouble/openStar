import { getBrowserStorage, readStoredString, removeStoredKey, writeStoredString } from '../stores/browserStorage.js'

const TOKEN_KEY = 'icore_access_token'
const USER_KEY = 'icore_current_user'

export function getAccessToken() {
  return readStoredString(getBrowserStorage(), TOKEN_KEY, '')
}

export function setSession(accessToken, user = null) {
  const storage = getBrowserStorage()
  if (accessToken) {
    writeStoredString(storage, TOKEN_KEY, accessToken)
  } else {
    removeStoredKey(storage, TOKEN_KEY)
  }
  if (user) {
    writeStoredString(storage, USER_KEY, JSON.stringify(user))
  } else {
    removeStoredKey(storage, USER_KEY)
  }
}

export function clearSession() {
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

export function buildAuthHeaders(extra = {}, tokenReader = getAccessToken) {
  const token = tokenReader()
  return token
    ? {
        ...extra,
        Authorization: `Bearer ${token}`,
      }
    : extra
}
