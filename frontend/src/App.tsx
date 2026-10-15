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
import { ErrorBanner } from './components/common/ErrorBanner';
import { useTheme } from './hooks/useTheme';
import './App.css';
import './MapPage.css';

export function App() {
  const [isDark, toggleTheme] = useTheme();

  const [mode, setMode] = useState<DataSourceMode>('live');
  const [, setSystemStatus] = useState<SystemStatus | null>(null);
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
    <div className={`app-root mp-root ${isDark ? 'theme-dark mp-root--dark' : 'theme-light'}`}>
      <StatusBar
        mode={mode}
        onToggleMode={handleToggleMode}
        isDark={isDark}
        onToggleTheme={toggleTheme}
        onOpenReportModal={() => {
          setPickedCoords(null);
          setIsReportFormOpen(true);
        }}
        onOpenForestModal={() => setIsForestModalOpen(true)}
      />

      <main className="mp-main">
        <aside className={`mp-sidebar ${isMobilePanelOpen ? 'is-open' : ''}`}>
          <div className="mp-sidebar__inner">
            {errorMessage && (
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
            )}

            <div className="mp-tabs" role="tablist" aria-label="Sumber data">
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'satelit'}
                className={`mp-tabs__item ${activeTab === 'satelit' ? 'is-active' : ''}`}
                onClick={() => setActiveTab('satelit')}
              >
                Deteksi Satelit
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'laporan'}
                className={`mp-tabs__item ${activeTab === 'laporan' ? 'is-active' : ''}`}
                onClick={() => setActiveTab('laporan')}
              >
                Laporan Warga
              </button>
            </div>

            {activeTab === 'satelit' ? (
              <>
                <FilterPanel
                  filters={filters}
                  onFilterChange={(newFilters) => setFilters(newFilters)}
                  onReset={handleResetFilters}
                  totalFiltered={hotspots.length}
                />

                <DetectionList
                  hotspots={hotspots}
                  isLoading={isLoading}
                  onSelectHotspot={(h) => setSelectedHotspot(h)}
                  selectedId={selectedHotspot?.id}
                  onExpandRange={() => setFilters((f) => ({ ...f, dayRange: 4, startDate: '', endDate: '' }))}
                />
              </>
            ) : (
              <div className="mp-reports">
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

            <footer className="mp-sidebar__footer">
              <p>
                Sistem FireGuard memadukan sensor termal satelit NASA FIRMS dan pelaporan partisipatif warga.
                Laporan masyarakat bertindak sebagai informasi awal dan diverifikasi bertahap.
              </p>
            </footer>
          </div>
        </aside>

        <button
          type="button"
          className="mp-drawer-toggle"
          onClick={() => setIsMobilePanelOpen((prev) => !prev)}
          aria-label={isMobilePanelOpen ? 'Tutup panel kontrol' : 'Buka panel kontrol'}
        >
          {isMobilePanelOpen ? 'Tutup Panel' : `Kontrol & Deteksi (${hotspots.length + reports.length})`}
        </button>

        <section className="mp-map-section" aria-label="Peta Interaktif Hotspot Indonesia">
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
