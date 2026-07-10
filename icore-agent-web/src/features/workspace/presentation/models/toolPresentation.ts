import type { Component } from 'vue'
import {
  Binary,
  BrainCircuit,
  Code2,
  Database,
  FilePenLine,
  FileSearch,
  Files,
  Globe2,
  ImagePlus,
  Search,
  ScanSearch,
  Send,
  Wrench,
} from 'lucide-vue-next'

import type { ToolCallItemPayload } from '../../domain/models/timeline'

export interface ToolPresentation {
  icon: Component
  labelKey: string | null
  fallbackLabel: string
}

const TOOL_PRESENTATIONS: Record<string, Omit<ToolPresentation, 'fallbackLabel'>> = {
  number_comparator: { icon: Binary, labelKey: 'chat.tools.number_comparator' },
  web_search: { icon: Search, labelKey: 'chat.tools.web_search' },
  fetch_webpage: { icon: Globe2, labelKey: 'chat.tools.fetch_webpage' },
  http_request: { icon: Send, labelKey: 'chat.tools.http_request' },
  run_python_snippet: { icon: Code2, labelKey: 'chat.tools.run_python_snippet' },
  list_files: { icon: Files, labelKey: 'chat.tools.list_files' },
  read_file: { icon: FileSearch, labelKey: 'chat.tools.read_file' },
  write_file: { icon: FilePenLine, labelKey: 'chat.tools.write_file' },
  read_uploaded_file: { icon: FileSearch, labelKey: 'chat.tools.read_uploaded_file' },
  chroma_search: { icon: Database, labelKey: 'chat.tools.chroma_search' },
  understand_image: { icon: ScanSearch, labelKey: 'chat.tools.understand_image' },
  generate_image: { icon: ImagePlus, labelKey: 'chat.tools.generate_image' },
  think: { icon: BrainCircuit, labelKey: 'chat.tools.think' },
}

/** Resolve a known tool visual while keeping unknown protocol tools usable. */
export function resolveToolPresentation(name: string): ToolPresentation {
  const normalized = name.trim()
  const known = TOOL_PRESENTATIONS[normalized]
  return {
    icon: known?.icon || Wrench,
    labelKey: known?.labelKey || null,
    fallbackLabel: humanizeToolName(normalized),
  }
}

/** Build a short, stable call summary from common tool argument fields. */
export function summarizeToolArguments(payload: ToolCallItemPayload): string {
  const args = readToolArguments(payload)
  const candidateKeys = ['query', 'url', 'path', 'filename', 'prompt', 'expression']
  for (const key of candidateKeys) {
    const value = args[key]
    if (typeof value === 'string' && value.trim()) return truncate(value.trim(), 96)
  }
  return ''
}

/** Format raw function arguments for the expandable technical detail area. */
export function formatToolArguments(payload: ToolCallItemPayload): string {
  const raw = payload.function.arguments_text.trim()
  if (raw) return prettyJson(raw)
  const args = payload.function.arguments_json
  return args ? JSON.stringify(args, null, 2) : ''
}

/** Return a concise single-line preview for a tool result. */
export function summarizeToolResult(payload: ToolCallItemPayload): string {
  const text = String(payload.result?.content || '').trim()
  return text ? truncate(text.replace(/\s+/g, ' '), 140) : ''
}

/** Read tool arguments from structured JSON or a complete streamed JSON string. */
function readToolArguments(payload: ToolCallItemPayload): Record<string, unknown> {
  if (payload.function.arguments_json) return payload.function.arguments_json
  const raw = payload.function.arguments_text.trim()
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? parsed as Record<string, unknown>
      : {}
  } catch {
    return {}
  }
}

/** Convert a protocol identifier into a readable generic fallback label. */
function humanizeToolName(name: string): string {
  if (!name) return 'Tool'
  return name
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

/** Pretty-print JSON when the streamed argument string is complete. */
function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

/** Truncate text without changing its meaning for short timeline previews. */
function truncate(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, maxLength - 3)}...` : value
}
