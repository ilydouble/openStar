/**
 * Normalize a file picker selection into a stable array for Commerce upload flows.
 * @param {FileList|File[]|null|undefined} selection
 * @returns {File[]}
 */
export function normalizeSelectedCsvFiles(selection) {
  return Array.from(selection || []).filter(Boolean)
}

/**
 * Upload every selected Commerce CSV before starting the batch diagnosis.
 * @param {FileList|File[]} selection
 * @param {{
 *   uploadFileAsset: (file: File) => Promise<Record<string, unknown>>,
 *   createCommerceDiagnosis: (fileUuids: string[], options?: { locale?: string }) => Promise<Record<string, unknown>>,
 *   locale: string,
 * }} deps
 * @returns {Promise<{ report: Record<string, unknown>, uploadedFiles: Record<string, unknown>[], sourceText: string }|null>}
 */
export async function uploadCsvFilesBeforeDiagnosis(selection, deps) {
  const files = normalizeSelectedCsvFiles(selection)
  if (files.length === 0) return null

  const uploadedFiles = await Promise.all(
    files.map((file) => deps.uploadFileAsset(file)),
  )
  const fileUuids = uploadedFiles
    .map((upload) => String(upload.file_uuid || '').trim())
    .filter(Boolean)
  const report = await deps.createCommerceDiagnosis(
    fileUuids,
    { locale: deps.locale },
  )

  return {
    report,
    uploadedFiles,
    sourceText: describeCommerceDiagnosisSource(files, uploadedFiles),
  }
}

/**
 * Build compact source copy for a completed Commerce CSV upload batch.
 * @param {File[]} files
 * @param {Record<string, unknown>[]} uploadedFiles
 * @returns {string}
 */
export function describeCommerceDiagnosisSource(files, uploadedFiles) {
  const firstUpload = uploadedFiles[0] || {}
  const firstFile = files[0] || {}
  const firstName = String(
    firstUpload.original_filename || firstUpload.filename || firstFile.name || '',
  )
  if (files.length <= 1) return firstName
  return `${firstName} + ${files.length - 1}`
}
