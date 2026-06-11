type EvidenceLike = {
  evidence_id?: unknown
  source_label?: unknown
  source_type?: unknown
  snippet?: unknown
  text?: unknown
  content?: unknown
}

function cleanText(value: unknown): string {
  if (value === null || value === undefined) return ''
  return String(value).trim()
}

export function formatEvidenceLabel(e: EvidenceLike): string {
  const id = cleanText(e.evidence_id)
  const label = cleanText(e.source_label) || cleanText(e.source_type) || '档案'
  return id ? `${id} · ${label}` : label
}

export function formatEvidenceSnippet(e: EvidenceLike, maxLength = 200): string {
  const raw = cleanText(e.snippet) || cleanText(e.text) || cleanText(e.content)
  return raw.length > maxLength ? raw.slice(0, maxLength) : raw
}