// @vitest-environment jsdom
import assert from 'node:assert/strict'
import { test } from 'vitest'
import { mount } from '@vue/test-utils'

import DocumentFileIcon from './DocumentFileIcon.vue'

test('document file icon selects the PDF presentation color', () => {
  const wrapper = mount(DocumentFileIcon, { props: { filename: 'report.pdf' } })

  assert.equal(wrapper.get('svg').classes().includes('text-red-600'), true)
})
