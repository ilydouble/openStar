import { getBrowserStorage, readStoredString, writeStoredString } from './browserStorage.js'

export const LOCALE_STORAGE_KEY = 'locale'

/**
 * Read the persisted locale for the international product, defaulting to Chinese.
 * @param {Storage | null | undefined} [storage]
 */
export function getLocalePreference(storage = getBrowserStorage()) {
  return readStoredString(storage, LOCALE_STORAGE_KEY, 'zh-CN') || 'zh-CN'
}

/**
 * Persist the selected locale for the current browser profile.
 * @param {string} locale
 * @param {Storage | null | undefined} [storage]
 */
export function setLocalePreference(locale, storage = getBrowserStorage()) {
  writeStoredString(storage, LOCALE_STORAGE_KEY, locale)
}
