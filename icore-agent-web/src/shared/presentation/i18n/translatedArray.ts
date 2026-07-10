/** Read one vue-i18n message array with an explicit consumer-owned item type. */
export function translatedArray<T>(translator: unknown, key: string): T[] {
  const translate = translator as (messageKey: string) => unknown
  const value = translate(key)
  return Array.isArray(value) ? value as T[] : []
}
