import assert from 'node:assert/strict'
import test from 'node:test'

import {
  normalizeSelectedCsvFiles,
  uploadCsvFilesBeforeDiagnosis,
} from './commerceDiagnosisUpload.js'

test('normalizeSelectedCsvFiles returns every selected CSV file', () => {
  const files = [
    { name: 'orders.csv' },
    { name: 'inventory.csv' },
  ]

  assert.deepEqual(normalizeSelectedCsvFiles(files), files)
})

test('uploadCsvFilesBeforeDiagnosis waits for all uploads before analysis', async () => {
  const events = []
  let finishFirstUpload
  let finishSecondUpload
  const files = [
    { name: 'orders.csv' },
    { name: 'inventory.csv' },
  ]

  const resultPromise = uploadCsvFilesBeforeDiagnosis(files, {
    locale: 'zh-CN',
    uploadFileAsset: async (file) => {
      events.push(`upload-start:${file.name}`)
      await new Promise((resolve) => {
        if (file.name === 'orders.csv') finishFirstUpload = resolve
        if (file.name === 'inventory.csv') finishSecondUpload = resolve
      })
      events.push(`upload-done:${file.name}`)
      return {
        file_uuid: `uuid-${file.name}`,
        original_filename: file.name,
      }
    },
    createCommerceDiagnosis: async (fileUuids, options) => {
      events.push(`diagnose:${fileUuids.join('|')}:${options.locale}`)
      return { diagnosis_id: 'diagnosis-1' }
    },
  })

  await Promise.resolve()
  assert.deepEqual(events, [
    'upload-start:orders.csv',
    'upload-start:inventory.csv',
  ])

  finishFirstUpload()
  await Promise.resolve()
  assert.deepEqual(events, [
    'upload-start:orders.csv',
    'upload-start:inventory.csv',
    'upload-done:orders.csv',
  ])

  finishSecondUpload()
  const result = await resultPromise

  assert.deepEqual(events, [
    'upload-start:orders.csv',
    'upload-start:inventory.csv',
    'upload-done:orders.csv',
    'upload-done:inventory.csv',
    'diagnose:uuid-orders.csv|uuid-inventory.csv:zh-CN',
  ])
  assert.equal(result.report.diagnosis_id, 'diagnosis-1')
  assert.equal(result.sourceText, 'orders.csv + 1')
})
