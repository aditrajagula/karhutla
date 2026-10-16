/**
 * Tipe data untuk Fitur Pelaporan Masyarakat (Citizen Reports).
 */

export type ReportCategory =
  | 'penebangan_liar'
  | 'pembukaan_lahan'
  | 'penambangan'
  | 'perambahan_hutan'
  | 'kebakaran'
  | 'perubahan_tutupan'
  | 'kebakaran_hutan';

export type ReportStatus = 'PENDING' | 'IN_REVIEW' | 'VERIFIED' | 'REJECTED';

export type EvidenceAssessmentCode = 'SUPPORTING_INDICATION' | 'NO_MATCH_FOUND' | 'INSUFFICIENT_DATA' | 'NOT_ASSESSED';

export type EvidenceAssessmentLabel = 'Ada indikasi pendukung' | 'Belum ditemukan kecocokan' | 'Belum dapat dinilai';

export interface EvidenceAssessment {
  assessment_code: EvidenceAssessmentCode;
  category_result: EvidenceAssessmentLabel;
  evidence_type: string;
  summary: string;
  matching_rule: string;
  details?: Record<string, unknown> | null;
  limitations_caveat: string;
}

export interface CitizenReport {
  id: string;
  category: ReportCategory;
  latitude: number;
  longitude: number;
  province?: string | null;
  observed_at_utc: string;
  description: string;
  photo_filename?: string | null;
  photo_url?: string | null;
  reporter_name?: string | null;
  // reporter_contact tidak pernah diekspos pada respon publik demi privasi warga
  status: ReportStatus;
  evidence_assessment?: EvidenceAssessment;
  environmental_risk?: {
    status?: string;
    risk_level?: string;
    risk_percentage?: number;
    risk_probability?: number;
    weather_source?: string;
    primary_drivers?: Array<{ feature: string; label: string; impact: string }>;
  } | null;
  verification_notes?: string | null;
  rejection_reason?: string | null;
  is_duplicate_suspect: boolean;
  duplicate_of_id?: string | null;
  created_at_utc: string;
  updated_at_utc: string;
}

export interface CreateCitizenReportPayload {
  category: ReportCategory;
  latitude: number;
  longitude: number;
  observed_at_utc: string;
  description: string;
  photo_base64?: string | null;
  reporter_name?: string | null;
  reporter_contact?: string | null;
}

export interface UpdateReportStatusPayload {
  status: ReportStatus;
  verification_notes?: string | null;
  rejection_reason?: string | null;
}

export interface CitizenReportsResponse {
  type: string;
  count: number;
  records: CitizenReport[];
  features?: unknown[];
}

export interface CreateReportResponse {
  status: string;
  message: string;
  is_duplicate_suspect: boolean;
  duplicate_of_id?: string | null;
  evidence_assessment?: EvidenceAssessment;
  data: CitizenReport;
}

export interface UpdateReportResponse {
  status: string;
  message: string;
  data: CitizenReport;
}

export const CATEGORY_LABELS: Record<ReportCategory, string> = {
  penebangan_liar: 'Penebangan Liar',
  pembukaan_lahan: 'Pembukaan Lahan',
  penambangan: 'Penambangan',
  perambahan_hutan: 'Perambahan Kawasan Hutan',
  kebakaran: 'Kebakaran Pembukaan Lahan (Slash & Burn)',
  perubahan_tutupan: 'Perubahan Drastis Tutupan Kanopi',
  kebakaran_hutan: 'Kebakaran Hutan & Lahan',
};

export const STATUS_LABELS: Record<ReportStatus, string> = {
  PENDING: 'Menunggu Verifikasi',
  IN_REVIEW: 'Perlu Pemeriksaan Lebih Lanjut',
  VERIFIED: 'Terverifikasi',
  REJECTED: 'Ditolak dengan Alasan',
};

export const EVIDENCE_BADGE_CONFIG: Record<
  EvidenceAssessmentLabel,
  { bg: string; text: string; border: string; icon: string }
> = {
  'Ada indikasi pendukung': {
    bg: 'rgba(239, 68, 68, 0.15)',
    text: '#ef4444',
    border: 'rgba(239, 68, 68, 0.4)',
    icon: '⚡',
  },
  'Belum ditemukan kecocokan': {
    bg: 'rgba(245, 158, 11, 0.15)',
    text: '#f59e0b',
    border: 'rgba(245, 158, 11, 0.4)',
    icon: '🔍',
  },
  'Belum dapat dinilai': {
    bg: 'rgba(107, 114, 128, 0.15)',
    text: '#9ca3af',
    border: 'rgba(107, 114, 128, 0.4)',
    icon: '⏳',
  },
};
