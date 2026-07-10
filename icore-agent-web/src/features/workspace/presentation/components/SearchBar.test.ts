// @vitest-environment jsdom
import assert from 'node:assert/strict'
import { test } from 'vitest'
import { mount } from '@vue/test-utils'

import i18n from '../../../../shared/presentation/i18n'
import SearchBar from './SearchBar.vue'

test('search bar emits a typed composer payload for text submission', async () => {
  const wrapper = mount(SearchBar, {
    global: { plugins: [i18n] },
  })
  const textarea = wrapper.get('textarea')

  await textarea.setValue('Run the market review')
  await textarea.trigger('keydown', { key: 'Enter' })

  assert.deepEqual(wrapper.emitted('submit')?.[0], [{
    message: 'Run the market review',
    imageFiles: [],
    dataFiles: [],
  }])
  wrapper.unmount()
})
