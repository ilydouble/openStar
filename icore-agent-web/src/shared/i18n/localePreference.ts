import { getBrowserStorage, readStoredString, writeStoredString } from '../storage/browserStorage'

export const LOCALE_STORAGE_KEY = 'locale'

/**
 * Read the currently persisted locale, defaulting to Simplified Chinese.
 */
export function getLocalePreference(storage: Storage | null | undefined = getBrowserStorage()): string {
  return readStoredString(storage, LOCALE_STORAGE_KEY, 'zh-CN') || 'zh-CN'
}

/**
 * Persist the selected locale for the current browser profile.
 */
export function setLocalePreference(
  locale: string,
  storage: Storage | null | undefined = getBrowserStorage(),
): void {
  writeStoredString(storage, LOCALE_STORAGE_KEY, locale)
}
