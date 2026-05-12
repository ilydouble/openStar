const TOKEN_KEY = 'icore_access_token'
const USER_KEY = 'icore_current_user'

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setSession(accessToken, user = null) {
  if (accessToken) {
    localStorage.setItem(TOKEN_KEY, accessToken)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  } else {
    localStorage.removeItem(USER_KEY)
  }
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY)
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

export function buildAuthHeaders(extra = {}) {
  const token = getAccessToken()
  return token
    ? {
        ...extra,
        Authorization: `Bearer ${token}`,
      }
    : extra
}
