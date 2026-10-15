import { useEffect, useState } from 'react';
import { fetchCitizenReportDetail, fetchNearbyReports } from '../../services/api';
import { fetchAlertSettings, saveAlertSettings } from '../../services/api';
import type { CitizenReport } from '../../types/report';

interface NearbyAlertsProps {
  onSelectReport: (report: CitizenReport) => void;
}

const RADIUS_OPTIONS = [1, 3, 5, 10];

export function NearbyAlerts({ onSelectReport }: NearbyAlertsProps) {
  const [enabled, setEnabled] = useState(
    false,
  );
  const [radiusKm, setRadiusKm] = useState(
    3,
  );
  const [records, setRecords] = useState<Awaited<ReturnType<typeof fetchNearbyReports>>['records']>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let ignore = false;
    void fetchAlertSettings()
      .then((settings) => {
        if (ignore) return;
        setEnabled(settings.enabled);
        setRadiusKm(settings.radius_m / 1000);
      })
      .catch((cause: unknown) => {
        if (!ignore) {
          setError(cause instanceof Error ? cause.message : 'Pengaturan alert gagal dimuat.');
        }
      });
    return () => {
      ignore = true;
    };
  }, []);

  const refresh = async (radius = radiusKm) => {
    if (!navigator.geolocation) {
      setError('Browser ini tidak menyediakan lokasi GPS.');
      setEnabled(false);
      try {
        await saveAlertSettings(false, radius * 1000);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Pengaturan alert gagal disimpan.');
      }
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          timeout: 10000,
          enableHighAccuracy: true,
          maximumAge: 60000,
        });
      });
      const result = await fetchNearbyReports(
        position.coords.latitude,
        position.coords.longitude,
        radius,
      );
      setRecords(result.records);
      setMessage(result.message);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : 'Izin lokasi ditolak atau daftar laporan tidak dapat dimuat.',
      );
      setRecords([]);
      setMessage(null);
      setEnabled(false);
      try {
        await saveAlertSettings(false, radius * 1000);
      } catch (settingError) {
        setError(settingError instanceof Error ? settingError.message : 'Pengaturan alert gagal disimpan.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (next: boolean) => {
    setLoading(true);
    setError(null);
    try {
      await saveAlertSettings(next, radiusKm * 1000);
      setEnabled(next);
      if (next) {
        await refresh();
      } else {
        setRecords([]);
        setMessage(null);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Pengaturan alert gagal disimpan.');
    } finally {
      setLoading(false);
    }
    if (!next) {
      setRecords([]);
      setMessage(null);
    }
  };

  return (
    <section
      aria-label="Alert laporan warga terdekat"
      style={{
        padding: '10px',
        background: 'var(--color-bg-card)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
      }}
    >
      <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, fontSize: '12px' }}>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => void handleToggle(event.target.checked)}
        />
        Alert laporan warga terdekat
      </label>
      <div style={{ margin: '6px 0', fontSize: '11px', color: 'var(--color-text-muted)' }}>
        Meminta GPS hanya saat Anda menyalakan atau memperbarui alert. Lokasi tidak disimpan.
      </div>
      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
        <label htmlFor="nearby-alert-radius" style={{ fontSize: '11px' }}>Radius:</label>
        <select
          id="nearby-alert-radius"
          value={radiusKm}
          onChange={(event) => {
            const next = Number(event.target.value);
            setRadiusKm(next);
            void saveAlertSettings(enabled, next * 1000)
              .then(() => enabled ? refresh(next) : undefined)
              .catch((cause: unknown) => {
                setError(cause instanceof Error ? cause.message : 'Radius alert gagal disimpan.');
              });
          }}
        >
          {RADIUS_OPTIONS.map((radius) => <option key={radius} value={radius}>{radius} km</option>)}
        </select>
        {enabled && (
          <button type="button" className="btn-action" disabled={loading} onClick={() => void refresh()}>
            {loading ? 'Memuat...' : 'Perbarui'}
          </button>
        )}
      </div>
      {error && <p role="alert" style={{ color: '#B91C1C', fontSize: '11px' }}>{error}</p>}
      {message && <p role="status" style={{ fontSize: '11px', lineHeight: 1.4 }}>{message}</p>}
      {records.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '11px' }}>
          {records.map((record) => (
            <li key={record.id} style={{ marginTop: '4px' }}>
              <button
                type="button"
                onClick={async () => {
                  try {
                    onSelectReport(await fetchCitizenReportDetail(record.id));
                  } catch (cause) {
                    setError(cause instanceof Error ? cause.message : 'Detail laporan gagal dimuat.');
                  }
                }}
                style={{ border: 0, background: 'none', color: 'var(--color-forest)', cursor: 'pointer', padding: 0 }}
              >
                {record.category.replaceAll('_', ' ')} · {record.distance_km} km · {record.observed_at_utc.slice(0, 10)}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div style={{ marginTop: '6px', fontSize: '10px', color: 'var(--color-text-muted)' }}>
        Bukan notifikasi darurat dan tidak menggunakan hotspot satelit.
      </div>
    </section>
  );
}
