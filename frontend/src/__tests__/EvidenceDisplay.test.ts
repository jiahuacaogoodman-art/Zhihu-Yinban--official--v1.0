import { describe, expect, it } from 'vitest'
import { formatEvidenceLabel, formatEvidenceSnippet } from '../utils/evidence'

describe('evidence display helpers', () => {
  it('renders backend Evidence snippets returned by nursing decision APIs', () => {
    const evidence = {
      evidence_id: 'E1',
      source_label: '病历OCR',
      source_type: 'medical_record_upload',
      snippet: '患者近三日血压偏高，夜间咳嗽加重。',
    }

    expect(formatEvidenceLabel(evidence)).toBe('E1 · 病历OCR')
    expect(formatEvidenceSnippet(evidence)).toBe('患者近三日血压偏高，夜间咳嗽加重。')
  })

  it('keeps old text/content shaped evidence readable', () => {
    expect(formatEvidenceSnippet({ text: '旧字段文本' })).toBe('旧字段文本')
    expect(formatEvidenceSnippet({ content: '任务卡依据' })).toBe('任务卡依据')
  })
})