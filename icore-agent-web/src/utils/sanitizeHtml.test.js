import assert from 'node:assert/strict'
import { test } from 'node:test'

import { renderMarkdown, sanitizeHtml } from '../shared/html/sanitizeHtml'

test('sanitizeHtml strips script tags and event handlers', () => {
  const dirty = '<p>Hello</p><script>alert(1)</script><img src=x onerror="alert(1)">'
  const clean = sanitizeHtml(dirty)

  assert.equal(clean.includes('<script'), false)
  assert.equal(clean.includes('onerror'), false)
  assert.ok(clean.includes('<p>Hello</p>'))
})

test('sanitizeHtml preserves mark tags used in search snippets', () => {
  const snippet = 'Review the <mark>budget</mark> proposal'
  const clean = sanitizeHtml(snippet)

  assert.equal(clean, snippet)
})

test('renderMarkdown parses markdown and removes unsafe HTML', () => {
  const dirty = '**Bold** and <img src=x onerror="alert(1)">'
  const html = renderMarkdown(dirty)

  assert.ok(html.includes('<strong>Bold</strong>'))
  assert.equal(html.includes('onerror'), false)
})

test('renderMarkdown returns nbsp for empty content', () => {
  assert.equal(renderMarkdown(''), '&nbsp;')
  assert.equal(renderMarkdown(null), '&nbsp;')
})
