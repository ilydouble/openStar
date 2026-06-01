import DOMPurify from 'isomorphic-dompurify'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

/** Sanitize raw HTML before binding with v-html. */
export function sanitizeHtml(html) {
  if (!html) return ''
  return DOMPurify.sanitize(html)
}

/** Parse markdown and sanitize the resulting HTML for safe v-html rendering. */
export function renderMarkdown(text) {
  if (!text) return '&nbsp;'
  return DOMPurify.sanitize(marked.parse(text))
}
