/** Return the lowercase extension including the dot, or an empty string. */
export function fileExtension(name: string): string {
  const value = String(name || '')
  const index = value.lastIndexOf('.')
  return index >= 0 ? value.slice(index).toLowerCase() : ''
}

/** Map a filename to a supported document icon kind. */
export type DocumentFileKind = 'word' | 'excel' | 'pdf' | 'text' | 'markdown' | 'generic'

export function resolveDocumentFileKind(filename: string): DocumentFileKind {
  switch (fileExtension(filename)) {
    case '.doc':
    case '.docx':
      return 'word'
    case '.xls':
    case '.xlsx':
    case '.csv':
      return 'excel'
    case '.pdf':
      return 'pdf'
    case '.txt':
      return 'text'
    case '.md':
      return 'markdown'
    default:
      return 'generic'
  }
}

/** Tailwind color classes for each document icon kind. */
export const DOCUMENT_FILE_ICON_COLORS: Record<DocumentFileKind, string> = {
  word: 'text-blue-600 dark:text-blue-400',
  excel: 'text-emerald-600 dark:text-emerald-400',
  pdf: 'text-red-600 dark:text-red-400',
  text: 'text-slate-600 dark:text-slate-400',
  markdown: 'text-violet-600 dark:text-violet-400',
  generic: 'text-zinc-600 dark:text-zinc-400',
}
