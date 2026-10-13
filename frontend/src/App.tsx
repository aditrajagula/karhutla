import { useEffect, useState, useMemo } from 'react';
import type { Hotspot, HotspotFilterParams } from './types/hotspot';
import type { DataSourceMode, SystemStatus } from './types/status';
import { getThermalCategory } from './types/hotspot';
import { fetchHotspots, fetchSystemStatus } from './services/api';
import { StatusBar } from './components/status/StatusBar';
import { MapContainer } from './components/map/MapContainer';
import { FilterPanel } from './components/filters/FilterPanel';
import { DetectionList } from './components/detection/DetectionList';
import { LoadingSpinner } from './components/common/LoadingSpinner';
import { EmptyState } from './components/common/EmptyState';
import { ErrorBanner } from './components/common/ErrorBanner';
import './App.css';

export function App() {
  const [isDark, setIsDark] = useState<boolean>(true); // Default Dark GIS Theme sesuai DSG v2.0 §1.1

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
    searchQuery: '',
    startDate: '',
    endDate: '',
    minConfidence: undefined,
    thermalTier: undefined,
  });

  // Sinkronisasi kelas tema di root document
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('theme-light');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('theme-light');
    }
  }, [isDark]);

  const { dayRange, startDate, endDate, minConfidence, satellite } = filters;

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
          dayRange,
          startDate,
          endDate,
          minConfidence,
          satellite,
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
                dayRange,
                startDate,
                endDate,
                minConfidence,
                satellite,
                mode: 'snapshot',
              });
              setHotspots(snapshotRes.records || []);
              setMode('snapshot');
              setErrorMessage('Data live tidak dapat diambil. Kami menampilkan snapshot statis benchmark.');
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
  }, [mode, dayRange, startDate, endDate, minConfidence, satellite, reloadTrigger]);

  // Filter client-side untuk pencarian kata kunci dan tingkat suhu (reaktif instan)
  const filteredHotspots = useMemo(() => {
    return hotspots.filter((h) => {
      if (filters.searchQuery) {
        const q = filters.searchQuery.toLowerCase().trim();
        const matchesProv = h.province && h.province.toLowerCase().includes(q);
        const matchesCoord = `${h.latitude},${h.longitude}`.includes(q);
        if (!matchesProv && !matchesCoord) return false;
      }
      if (filters.thermalTier) {
        const cat = getThermalCategory(h.frp);
        if (cat.tier !== filters.thermalTier) return false;
      }
      return true;
    });
  }, [hotspots, filters.searchQuery, filters.thermalTier]);

  const handleToggleMode = () => {
    const nextMode: DataSourceMode = mode === 'live' ? 'snapshot' : 'live';
    setMode(nextMode);
  };

  const handleResetFilters = () => {
    setFilters({
      dayRange: 2,
      searchQuery: '',
      startDate: '',
      endDate: '',
      minConfidence: undefined,
      thermalTier: undefined,
    });
  };

  return (
    <div className={`app-root ${isDark ? 'dark' : 'theme-light'}`}>
      <main className="dashboard-layout">
        {/* Sidebar Kontrol (Sisi Kiri sesuai DSG v2.0 §5.1) */}
        <aside className={`sidebar-control-left ${isMobilePanelOpen ? 'mobile-open' : ''}`}>
          {/* Header Brand & Live Status Badge */}
          <StatusBar
            mode={mode}
            lastSyncUtc={systemStatus?.lastSyncUtc || null}
            onToggleMode={handleToggleMode}
            isDark={isDark}
            onToggleTheme={() => setIsDark((prev) => !prev)}
            totalCount={filteredHotspots.length}
          />

          <div className="sidebar-scrollable-content">
            {/* Banner Error / Notifikasi Fallback */}
            {errorMessage && (
              <div className="sidebar-section">
                <ErrorBanner
                  title="Data live tidak dapat diambil"
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

            {/* Filter Bar (Search + Pill Dropdowns) Sesuai DSG §5.1 */}
            <div className="sidebar-section">
              <FilterPanel
                filters={filters}
                onFilterChange={(newFilters) => setFilters(newFilters)}
                onReset={handleResetFilters}
                totalFiltered={filteredHotspots.length}
              />
            </div>

            {/* Hotspot Item Cards / Loading / Empty */}
            <div className="sidebar-section list-section">
              {isLoading ? (
                <LoadingSpinner label="Memuat deteksi anomali satelit…" />
              ) : filteredHotspots.length === 0 ? (
                <EmptyState
                  title="Tidak ada deteksi pada periode ini"
                  message="Tidak ada anomali termal terdeteksi pada filter ini. Hal ini bukan jaminan ketiadaan api di lapangan."
                  actionLabel="Perluas ke 7 Hari"
                  onAction={() => setFilters((f) => ({ ...f, dayRange: 7, searchQuery: '', thermalTier: undefined }))}
                />
              ) : (
                <DetectionList
                  hotspots={filteredHotspots}
                  onSelectHotspot={(h) => setSelectedHotspot(h)}
                  selectedId={selectedHotspot?.id}
                />
              )}
            </div>
          </div>

          {/* Disclaimer Faktual Sesuai DSG §6 */}
          <div className="sidebar-footer">
            <p>
              Data satelit NASA FIRMS VIIRS (NOAA-20 / Suomi NPP).
              Anomali termal mengindikasikan suhu sensorik, bukan kepastian kebakaran lahan.
            </p>
          </div>
        </aside>

        {/* Mobile Toggle Button */}
        <button
          type="button"
          className="mobile-drawer-toggle"
          onClick={() => setIsMobilePanelOpen((prev) => !prev)}
          aria-label={isMobilePanelOpen ? 'Tutup panel kontrol' : 'Buka panel kontrol'}
        >
          {isMobilePanelOpen ? 'Tutup Panel' : `Daftar Deteksi (${filteredHotspots.length})`}
        </button>

        {/* Kanvas Peta Interaktif (Sisi Kanan / Penuh) */}
        <section className="map-view-right" aria-label="Peta Interaktif Hotspot Indonesia">
          <MapContainer
            hotspots={filteredHotspots}
            selectedHotspot={selectedHotspot}
            onSelectHotspot={(h) => setSelectedHotspot(h)}
            isDark={isDark}
          />
        </section>
      </main>
    </div>
  );
}

export default App;
