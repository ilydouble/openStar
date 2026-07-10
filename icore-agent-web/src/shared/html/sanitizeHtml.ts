import DOMPurify from 'isomorphic-dompurify'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

/** Sanitize raw HTML before binding with v-html. */
export function sanitizeHtml(html: string): string {
  if (!html) return ''
  return DOMPurify.sanitize(html)
}

/** Parse markdown and sanitize the resulting HTML for safe v-html rendering. */
export function renderMarkdown(text: string): string {
  if (!text) return '&nbsp;'
  const rendered = marked.parse(text)
  return DOMPurify.sanitize(typeof rendered === 'string' ? rendered : '')
}
