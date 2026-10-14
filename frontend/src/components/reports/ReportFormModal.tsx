import React, { useState } from 'react';
import type { CreateCitizenReportPayload, ReportCategory } from '../../types/report';
import { CATEGORY_LABELS } from '../../types/report';
import { submitCitizenReport } from '../../services/api';

interface ReportFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialCoords?: { lat: number; lng: number } | null;
  onPickOnMapRequest?: () => void;
}

export const ReportFormModal: React.FC<ReportFormModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  initialCoords,
  onPickOnMapRequest,
}) => {
  const [category, setCategory] = useState<ReportCategory>('kebakaran');
  const [latitude, setLatitude] = useState<string>(
    initialCoords ? initialCoords.lat.toFixed(5) : ''
  );
  const [longitude, setLongitude] = useState<string>(
    initialCoords ? initialCoords.lng.toFixed(5) : ''
  );
  const [observedAt, setObservedAt] = useState<string>(() => {
    const now = new Date();
    // Format YYYY-MM-DDTHH:mm untuk datetime-local
    return now.toISOString().slice(0, 16);
  });
  const [description, setDescription] = useState<string>('');
  const [reporterName, setReporterName] = useState<string>('');
  const [reporterContact, setReporterContact] = useState<string>('');
  const [photoBase64, setPhotoBase64] = useState<string | null>(null);
  const [photoFileName, setPhotoFileName] = useState<string>('');

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<{
    id: string;
    message: string;
    isDuplicate: boolean;
  } | null>(null);
  const [isLocating, setIsLocating] = useState<boolean>(false);

  // Perbarui koordinat jika initialCoords berubah dari klik peta
  React.useEffect(() => {
    if (initialCoords) {
      setLatitude(initialCoords.lat.toFixed(5));
      setLongitude(initialCoords.lng.toFixed(5));
    }
  }, [initialCoords]);

  if (!isOpen) return null;

  const handleGetGPS = () => {
    if (!navigator.geolocation) {
      setErrorMessage('Browser tidak mendukung pendeteksian lokasi GPS.');
      return;
    }
    setIsLocating(true);
    setErrorMessage(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLatitude(pos.coords.latitude.toFixed(5));
        setLongitude(pos.coords.longitude.toFixed(5));
        setIsLocating(false);
      },
      (err) => {
        setIsLocating(false);
        setErrorMessage(`Gagal mendeteksi lokasi GPS: ${err.message}. Masukkan koordinat manual atau pilih di peta.`);
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      setErrorMessage('Berkas harus berupa file gambar (JPG, PNG, atau WEBP).');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setErrorMessage('Ukuran file foto maksimal 5 MB.');
      return;
    }

    setPhotoFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      setPhotoBase64(reader.result as string);
      setErrorMessage(null);
    };
    reader.readAsDataURL(file);
  };

  const handleRemovePhoto = () => {
    setPhotoBase64(null);
    setPhotoFileName('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const latNum = parseFloat(latitude);
    const lonNum = parseFloat(longitude);

    if (isNaN(latNum) || latNum < -11.0 || latNum > 6.0) {
      setErrorMessage('Latitude harus berupa angka dalam rentang daratan Indonesia (-11.0 s.d. 6.0).');
      return;
    }
    if (isNaN(lonNum) || lonNum < 95.0 || lonNum > 141.5) {
      setErrorMessage('Longitude harus berupa angka dalam rentang daratan Indonesia (95.0 s.d. 141.5).');
      return;
    }

    if (!description || description.trim().length < 10) {
      setErrorMessage('Deskripsi laporan wajib diisi minimal 10 karakter.');
      return;
    }

    if (!observedAt) {
      setErrorMessage('Waktu pengamatan kejadian wajib diisi.');
      return;
    }

    const obsDate = new Date(observedAt);
    if (obsDate.getTime() > Date.now() + 60 * 60 * 1000) {
      setErrorMessage('Waktu pengamatan tidak boleh berada di masa depan.');
      return;
    }

    setIsSubmitting(true);

    try {
      const payload: CreateCitizenReportPayload = {
        category,
        latitude: latNum,
        longitude: lonNum,
        observed_at_utc: obsDate.toISOString(),
        description: description.trim(),
        reporter_name: reporterName.trim() || undefined,
        reporter_contact: reporterContact.trim() || undefined,
        photo_base64: photoBase64,
      };

      const res = await submitCitizenReport(payload);
      setSuccessInfo({
        id: res.data.id,
        message: res.message,
        isDuplicate: res.is_duplicate_suspect,
      });
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Terjadi kegagalan saat mengirim laporan.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="report-modal-title"
      className="modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) onClose();
      }}
    >
      <div className="modal-card report-form-card" style={{ maxWidth: '560px', maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '18px' }}>📢</span>
            <h3 id="report-modal-title" className="modal-title">
              Pelaporan Kejadian Lapangan oleh Warga
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Tutup modal pelaporan"
            className="modal-close-btn"
          >
            ✕
          </button>
        </div>

        {successInfo ? (
          <div className="modal-body" style={{ textAlign: 'center', padding: '24px 16px' }}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>✅</div>
            <h4 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--color-text-main)', marginBottom: '8px' }}>
              Laporan Berhasil Terkirim
            </h4>
            <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '16px', lineHeight: 1.5 }}>
              {successInfo.message}
            </p>
            <div
              style={{
                background: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-border)',
                borderRadius: '6px',
                padding: '12px',
                fontSize: '12px',
                marginBottom: '18px',
                textAlign: 'left',
              }}
            >
              <div><b>Nomor ID Laporan:</b> <code className="font-mono">{successInfo.id}</code></div>
              <div style={{ marginTop: '4px' }}><b>Status Awal:</b> <span className="badge-status status-PENDING">Menunggu Verifikasi</span></div>
              {successInfo.isDuplicate && (
                <div style={{ marginTop: '6px', color: '#D97706', fontSize: '11px' }}>
                  ⚠️ Terdeteksi laporan serupa di lokasi terdekat. Laporan tetap tersimpan untuk ditinjau operator.
                </div>
              )}
            </div>
            <p style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '20px' }}>
              Laporan warga digunakan sebagai informasi awal untuk ditinjau oleh operator, bukan sebagai konfirmasi otomatis kebakaran atau deforestasi.
            </p>
            <button
              type="button"
              className="btn-action"
              style={{ minWidth: '140px', background: 'var(--color-forest-dark)', color: '#fff', border: 'none' }}
              onClick={onClose}
            >
              Selesai & Tutup
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="modal-body">
              {errorMessage && (
                <div
                  style={{
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid #EF4444',
                    color: '#B91C1C',
                    padding: '10px 12px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    marginBottom: '14px',
                    lineHeight: 1.4,
                  }}
                >
                  ⚠️ {errorMessage}
                </div>
              )}

              {/* Kategori Kejadian */}
              <div className="filter-group" style={{ marginBottom: '14px' }}>
                <label className="filter-label" htmlFor="report-category">
                  Kategori Kejadian <span style={{ color: '#EF4444' }}>*</span>
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '8px' }}>
                  {(['kebakaran', 'pembukaan_lahan', 'perubahan_tutupan'] as ReportCategory[]).map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      className={`btn-day ${category === cat ? 'active' : ''}`}
                      style={{ padding: '8px 10px', fontSize: '12px', textAlign: 'left', height: 'auto' }}
                      onClick={() => setCategory(cat)}
                    >
                      <div style={{ fontWeight: 600 }}>
                        {cat === 'kebakaran' ? '🔥 Kebakaran / Asap' : cat === 'pembukaan_lahan' ? '🚜 Pembukaan Lahan' : '🌲 Perubahan Tutupan'}
                      </div>
                      <div style={{ fontSize: '10px', opacity: 0.8, marginTop: '2px' }}>
                        {CATEGORY_LABELS[cat]}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Lokasi Koordinat */}
              <div className="filter-group" style={{ marginBottom: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <label className="filter-label" style={{ marginBottom: 0 }}>
                    Koordinat Lokasi Kejadian <span style={{ color: '#EF4444' }}>*</span>
                  </label>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      onClick={handleGetGPS}
                      disabled={isLocating}
                      className="btn-action"
                      style={{ fontSize: '11px', padding: '3px 8px', minHeight: '28px' }}
                      title="Ambil koordinat perangkat saat ini"
                    >
                      {isLocating ? 'Mencari GPS...' : '📍 GPS Saya'}
                    </button>
                    {onPickOnMapRequest && (
                      <button
                        type="button"
                        onClick={onPickOnMapRequest}
                        className="btn-action"
                        style={{ fontSize: '11px', padding: '3px 8px', minHeight: '28px' }}
                        title="Tutup form dan klik titik langsung pada peta"
                      >
                        🗺️ Pilih di Peta
                      </button>
                    )}
                  </div>
                </div>
                <div className="filter-date-grid">
                  <div>
                    <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Latitude:</span>
                    <input
                      type="number"
                      step="any"
                      placeholder="Contoh: -0.5234"
                      value={latitude}
                      onChange={(e) => setLatitude(e.target.value)}
                      className="filter-input font-mono"
                      required
                    />
                  </div>
                  <div>
                    <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Longitude:</span>
                    <input
                      type="number"
                      step="any"
                      placeholder="Contoh: 101.4421"
                      value={longitude}
                      onChange={(e) => setLongitude(e.target.value)}
                      className="filter-input font-mono"
                      required
                    />
                  </div>
                </div>
                <span style={{ fontSize: '10px', color: 'var(--color-text-muted)', display: 'block', marginTop: '3px' }}>
                  Batas koordinat daratan Indonesia (-11.0 s.d. 6.0 Lat, 95.0 s.d. 141.5 Lon).
                </span>
              </div>

              {/* Waktu Pengamatan */}
              <div className="filter-group" style={{ marginBottom: '14px' }}>
                <label className="filter-label" htmlFor="report-time">
                  Waktu Pengamatan Kejadian <span style={{ color: '#EF4444' }}>*</span>
                </label>
                <input
                  id="report-time"
                  type="datetime-local"
                  value={observedAt}
                  onChange={(e) => setObservedAt(e.target.value)}
                  className="filter-input"
                  required
                />
              </div>

              {/* Deskripsi Pengamatan */}
              <div className="filter-group" style={{ marginBottom: '14px' }}>
                <label className="filter-label" htmlFor="report-desc">
                  Deskripsi / Keterangan Kejadian <span style={{ color: '#EF4444' }}>*</span>
                </label>
                <textarea
                  id="report-desc"
                  rows={3}
                  placeholder="Ceritakan detail pengamatan Anda (misal: asap pekat tercium di tepi kanal gambut, perkiraan arah, atau ciri tutupan lahan)..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="filter-input"
                  style={{ width: '100%', resize: 'vertical' }}
                  required
                />
                <span style={{ fontSize: '10px', color: 'var(--color-text-muted)', display: 'block', marginTop: '2px' }}>
                  Minimal 10 karakter ({description.trim().length}/2000).
                </span>
              </div>

              {/* Foto Bukti Opsional */}
              <div className="filter-group" style={{ marginBottom: '14px' }}>
                <label className="filter-label">
                  Foto Pendukung (Opsional)
                </label>
                {photoBase64 ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
                    <img
                      src={photoBase64}
                      alt="Pratinjau foto laporan"
                      style={{ width: '64px', height: '64px', objectFit: 'cover', borderRadius: '4px', border: '1px solid var(--color-border)' }}
                    />
                    <div style={{ flex: 1, fontSize: '12px' }}>
                      <div style={{ fontWeight: 500, color: 'var(--color-text-main)' }}>{photoFileName || 'Foto Terlampir'}</div>
                      <button
                        type="button"
                        onClick={handleRemovePhoto}
                        style={{ color: '#EF4444', background: 'none', border: 'none', cursor: 'pointer', fontSize: '11px', padding: 0, marginTop: '2px' }}
                      >
                        Hapus Foto
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handlePhotoUpload}
                      className="filter-input"
                      style={{ fontSize: '12px' }}
                    />
                    <span style={{ fontSize: '10px', color: 'var(--color-text-muted)', display: 'block', marginTop: '2px' }}>
                      Format didukung: JPG, PNG, WEBP. Maksimal 5 MB.
                    </span>
                  </div>
                )}
              </div>

              {/* Data Pelapor (Opsional) */}
              <div className="filter-group" style={{ marginBottom: '8px' }}>
                <label className="filter-label">
                  Identitas Pelapor (Opsional)
                </label>
                <div className="filter-date-grid">
                  <input
                    type="text"
                    placeholder="Nama Pelapor (opsional)"
                    value={reporterName}
                    onChange={(e) => setReporterName(e.target.value)}
                    className="filter-input"
                  />
                  <input
                    type="text"
                    placeholder="No. Telp / Email (opsional)"
                    value={reporterContact}
                    onChange={(e) => setReporterContact(e.target.value)}
                    className="filter-input"
                  />
                </div>
              </div>
            </div>

            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                onClick={onClose}
                disabled={isSubmitting}
                className="btn-reset"
              >
                Batal
              </button>
              <button
                type="submit"
                disabled={isSubmitting}
                className="btn-action"
                style={{
                  background: 'var(--color-forest)',
                  color: '#F8FAFC',
                  fontWeight: 600,
                  minWidth: '120px',
                }}
              >
                {isSubmitting ? 'Mengirim...' : 'Kirim Laporan'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
