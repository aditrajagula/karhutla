import { useEffect, useState } from 'react';
import type { Hotspot, HotspotFilterParams } from './types/hotspot';
import type { DataSourceMode, SystemStatus } from './types/status';
import { fetchHotspots, fetchSystemStatus } from './services/api';
import { StatusBar } from './components/status/StatusBar';
import { MapContainer } from './components/map/MapContainer';
import { FilterPanel } from './components/filters/FilterPanel';
import { DetectionList } from './components/detection/DetectionList';
import { HotspotDetailModal } from './components/detection/HotspotDetailModal';
import { LoadingSpinner } from './components/common/LoadingSpinner';
import { EmptyState } from './components/common/EmptyState';
import { ErrorBanner } from './components/common/ErrorBanner';
import './App.css';

export function App() {
  const [isDark, setIsDark] = useState<boolean>(() => {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  const [mode, setMode] = useState<DataSourceMode>('live');
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [selectedHotspot, setSelectedHotspot] = useState<Hotspot | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isMobilePanelOpen, setIsMobilePanelOpen] = useState<boolean>(false);
  const [reloadTrigger, setReloadTrigger] = useState<number>(0);

  const [filters, setFilters] = useState<HotspotFilterParams>({
    dayRange: 2,
    startDate: '',
    endDate: '',
    minConfidence: undefined,
  });

  // Sinkronisasi kelas tema di root document
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  // Muat data dari backend
  useEffect(() => {
    let ignore = false;

    const executeFetch = async () => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        try {
          const statusRes = await fetchSystemStatus();
          if (!ignore) setSystemStatus(statusRes);
        } catch {
          // Status call minor
        }

        const res = await fetchHotspots({
          ...filters,
          mode,
        });

        if (!ignore) {
          setHotspots(res.records || []);
          if (res.mode === 'snapshot' && mode === 'live') {
            setMode('snapshot');
            if (res.message) {
              setErrorMessage(res.message);
            }
          }
        }
      } catch (err: unknown) {
        if (!ignore) {
          const msg = err instanceof Error ? err.message : 'Gagal menghubungi backend API';
          setErrorMessage(msg);
          if (mode === 'live') {
            try {
              const snapshotRes = await fetchHotspots({
                ...filters,
                mode: 'snapshot',
              });
              setHotspots(snapshotRes.records || []);
              setMode('snapshot');
              setErrorMessage('Gagal menghubungi NASA FIRMS API. Menampilkan snapshot lokal 7 hari (Benchmark JOINTS 2026).');
            } catch {
              setHotspots([]);
            }
          }
        }
      } finally {
        if (!ignore) {
          setIsLoading(false);
        }
      }
    };

    void Promise.resolve().then(executeFetch);

    return () => {
      ignore = true;
    };
  }, [mode, filters, reloadTrigger]);

  const handleToggleMode = () => {
    const nextMode: DataSourceMode = mode === 'live' ? 'snapshot' : 'live';
    setMode(nextMode);
  };

  const handleResetFilters = () => {
    setFilters({
      dayRange: 2,
      startDate: '',
      endDate: '',
      minConfidence: undefined,
    });
  };

  return (
    <div className={`app-root ${isDark ? 'theme-dark' : 'theme-light'}`}>
      {/* Top Bar Header */}
      <StatusBar
        mode={mode}
        lastSyncUtc={systemStatus?.lastSyncUtc || null}
        onToggleMode={handleToggleMode}
        isDark={isDark}
        onToggleTheme={() => setIsDark((prev) => !prev)}
        totalCount={hotspots.length}
      />

      {/* Main Container: Map-first Full Viewport Layout */}
      <main className="main-viewport">
        {/* Sidebar Kontrol (Desktop) & Collapsible Drawer (Mobile) */}
        <aside className={`sidebar-container ${isMobilePanelOpen ? 'mobile-open' : ''}`}>
          <div className="sidebar-inner">
            {/* Banner Error / Notifikasi Fallback */}
            {errorMessage && (
              <div className="sidebar-section">
                <ErrorBanner
                  message={errorMessage}
                  onRetry={() => {
                    setMode('live');
                    setReloadTrigger((n) => n + 1);
                  }}
                  onSwitchToSnapshot={() => {
                    setMode('snapshot');
                    setReloadTrigger((n) => n + 1);
                  }}
                />
              </div>
            )}

            {/* Panel Filter */}
            <div className="sidebar-section">
              <FilterPanel
                filters={filters}
                onFilterChange={(newFilters) => setFilters(newFilters)}
                onReset={handleResetFilters}
                totalFiltered={hotspots.length}
              />
            </div>

            {/* List Deteksi / Loading / Empty */}
            <div className="sidebar-section list-section">
              {isLoading ? (
                <LoadingSpinner label="Mengambil deteksi satelit FIRMS untuk wilayah terpilih..." />
              ) : hotspots.length === 0 ? (
                <EmptyState
                  message="Tidak ada anomali termal terdeteksi oleh satelit VIIRS pada rentang waktu terpilih di wilayah Indonesia."
                  actionLabel="Perluas Rentang ke 7 Hari"
                  onAction={() => setFilters((f) => ({ ...f, dayRange: 7, startDate: '', endDate: '' }))}
                />
              ) : (
                <DetectionList
                  hotspots={hotspots}
                  onSelectHotspot={(h) => setSelectedHotspot(h)}
                  selectedId={selectedHotspot?.id}
                />
              )}
            </div>

            {/* Disclaimer Faktual */}
            <div className="sidebar-footer">
              <p>
                Data satelit NASA FIRMS VIIRS (NOAA-20 / Suomi NPP).
                Anomali termal merupakan indikasi sensor satelit, bukan kepastian kebakaran.
              </p>
            </div>
          </div>
        </aside>

        {/* Tombol Toggle Drawer untuk Mobile */}
        <button
          type="button"
          className="mobile-drawer-toggle"
          onClick={() => setIsMobilePanelOpen((prev) => !prev)}
          aria-label={isMobilePanelOpen ? 'Tutup panel kontrol' : 'Buka panel kontrol'}
        >
          {isMobilePanelOpen ? 'Tutup Panel' : `Kontrol & Deteksi (${hotspots.length})`}
        </button>

        {/* Map Canvas Kanvas Peta Interaktif */}
        <section className="map-section" aria-label="Peta Interaktif Hotspot Indonesia">
          <MapContainer
            hotspots={hotspots}
            selectedHotspot={selectedHotspot}
            onSelectHotspot={(h) => setSelectedHotspot(h)}
            isDark={isDark}
          />
        </section>
      </main>

      {/* Modal Detail Titik Terpilih */}
      <HotspotDetailModal
        hotspot={selectedHotspot}
        onClose={() => setSelectedHotspot(null)}
      />
    </div>
  );
}

export default App;
