import { useEffect, useState } from 'react';
import type { Hotspot, HotspotFilterParams } from './types/hotspot';
import type { CitizenReport } from './types/report';
import type { DataSourceMode, SystemStatus } from './types/status';
import { fetchCitizenReports, fetchHotspots, fetchSystemStatus } from './services/api';
import { StatusBar } from './components/status/StatusBar';
import { MapContainer } from './components/map/MapContainer';
import { FilterPanel } from './components/filters/FilterPanel';
import { DetectionList } from './components/detection/DetectionList';
import { HotspotDetailModal } from './components/detection/HotspotDetailModal';
import { ReportFormModal } from './components/reports/ReportFormModal';
import { ReportDetailModal } from './components/reports/ReportDetailModal';
import { ReportList } from './components/reports/ReportList';
import { ForestLossModal } from './components/forest/ForestLossModal';
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

  // Data pelaporan masyarakat
  const [reports, setReports] = useState<CitizenReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<CitizenReport | null>(null);
  const [activeTab, setActiveTab] = useState<'satelit' | 'laporan'>('satelit');

  // Modal pelaporan & mode pilih koordinat peta
  const [isReportFormOpen, setIsReportFormOpen] = useState<boolean>(false);
  const [isForestModalOpen, setIsForestModalOpen] = useState<boolean>(false);
  const [isPickingLocation, setIsPickingLocation] = useState<boolean>(false);
  const [pickedCoords, setPickedCoords] = useState<{ lat: number; lng: number } | null>(null);

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

  // Muat data dari backend (Hotspot Satelit & Laporan Warga)
  useEffect(() => {
    let ignore = false;

    const executeFetch = async () => {
      setIsLoading(true);
      setErrorMessage(null);

      try {
        // Ambil status sistem
        try {
          const statusRes = await fetchSystemStatus();
          if (!ignore) setSystemStatus(statusRes);
        } catch {
          // Status call minor
        }

        // Ambil data hotspot satelit
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

        // Ambil data laporan warga
        try {
          const repRes = await fetchCitizenReports();
          if (!ignore) {
            setReports(repRes.records || []);
          }
        } catch {
          // Gagal laporan warga bersifat non-fatal bagi alur satelit
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
              setErrorMessage('Gagal menghubungi NASA FIRMS API. Menampilkan snapshot lokal tim.');
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

  // Muat ulang daftar laporan warga setelah laporan baru dibuat atau status diubah
  const handleReloadReports = async () => {
    try {
      const repRes = await fetchCitizenReports();
      setReports(repRes.records || []);
    } catch {
      // ignore
    }
  };

  // Handler saat tombol 'Pilih di Peta' pada form ditekan
  const handleRequestPickOnMap = () => {
    setIsReportFormOpen(false);
    setIsPickingLocation(true);
  };

  // Handler saat titik pada peta diklik
  const handleLocationPicked = (coords: { lat: number; lng: number }) => {
    setPickedCoords(coords);
    setIsPickingLocation(false);
    setIsReportFormOpen(true);
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
        reportsCount={reports.length}
        onOpenReportModal={() => {
          setPickedCoords(null);
          setIsReportFormOpen(true);
        }}
        onOpenForestModal={() => setIsForestModalOpen(true)}
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

            {/* Tab Navigasi Antara Satelit & Laporan Warga */}
            <div className="sidebar-section">
              <div className="sidebar-tabs">
                <button
                  type="button"
                  className={`tab-btn ${activeTab === 'satelit' ? 'active' : ''}`}
                  onClick={() => setActiveTab('satelit')}
                >
                  <span>🔥</span>
                  <span>Satelit FIRMS ({hotspots.length})</span>
                </button>
                <button
                  type="button"
                  className={`tab-btn ${activeTab === 'laporan' ? 'active' : ''}`}
                  onClick={() => setActiveTab('laporan')}
                >
                  <span>📢</span>
                  <span>Laporan Warga ({reports.length})</span>
                </button>
              </div>
            </div>

            {activeTab === 'satelit' ? (
              <>
                {/* Panel Filter Observasi Satelit */}
                <div className="sidebar-section">
                  <FilterPanel
                    filters={filters}
                    onFilterChange={(newFilters) => setFilters(newFilters)}
                    onReset={handleResetFilters}
                    totalFiltered={hotspots.length}
                  />
                </div>

                {/* List Deteksi Satelit */}
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
              </>
            ) : (
              /* Panel Laporan Partisipasi Warga */
              <div className="sidebar-section list-section" style={{ flex: 1 }}>
                <ReportList
                  reports={reports}
                  onSelectReport={(r) => setSelectedReport(r)}
                  selectedId={selectedReport?.id}
                  onOpenCreateModal={() => {
                    setPickedCoords(null);
                    setIsReportFormOpen(true);
                  }}
                />
              </div>
            )}

            {/* Disclaimer Faktual */}
            <div className="sidebar-footer">
              <p>
                Sistem FireGuard memadukan sensor termal satelit NASA FIRMS dan pelaporan partisipatif warga.
                Laporan masyarakat bertindak sebagai informasi awal dan diverifikasi bertahap.
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
          {isMobilePanelOpen ? 'Tutup Panel' : `Kontrol & Deteksi (${hotspots.length + reports.length})`}
        </button>

        {/* Map Canvas Kanvas Peta Interaktif */}
        <section className="map-section" aria-label="Peta Interaktif Hotspot Indonesia">
          <MapContainer
            hotspots={hotspots}
            selectedHotspot={selectedHotspot}
            onSelectHotspot={(h) => setSelectedHotspot(h)}
            reports={reports}
            selectedReport={selectedReport}
            onSelectReport={(r) => setSelectedReport(r)}
            isPickingLocation={isPickingLocation}
            onLocationPicked={handleLocationPicked}
            onCancelPickLocation={() => setIsPickingLocation(false)}
            isDark={isDark}
          />
        </section>
      </main>

      {/* Modal Detail Titik Hotspot Satelit */}
      <HotspotDetailModal
        hotspot={selectedHotspot}
        onClose={() => setSelectedHotspot(null)}
      />

      {/* Modal Form Pelaporan Masyarakat */}
      <ReportFormModal
        isOpen={isReportFormOpen}
        onClose={() => setIsReportFormOpen(false)}
        onSuccess={handleReloadReports}
        initialCoords={pickedCoords}
        onPickOnMapRequest={handleRequestPickOnMap}
      />

      {/* Modal Detail Laporan Masyarakat */}
      <ReportDetailModal
        report={selectedReport}
        onClose={() => setSelectedReport(null)}
      />

      {/* Modal Analisis Tutupan Pohon Hansen GFC */}
      <ForestLossModal
        isOpen={isForestModalOpen}
        onClose={() => setIsForestModalOpen(false)}
        isDark={isDark}
      />
    </div>
  );
}

export default App;
