/**
 * Sinkronisasi Laporan Partisipasi Warga secara Real-Time.
 * Mendukung sinkronisasi instan antar-tab/jendela (BroadcastChannel & StorageEvent)
 * tanpa perlu memuat ulang seluruh halaman ataupun mengunduh ulang titik FIRMS.
 */

const REPORTS_CHANNEL_NAME = 'jagaborneo_reports_sync_channel';
const REPORTS_STORAGE_KEY = 'jb_reports_last_sync_timestamp';

export interface ReportSyncMessage {
  type: 'REPORTS_CHANGED';
  timestamp: number;
}

/**
 * Mengirimkan sinyal pemberitahuan ke semua tab/jendela lain bahwa data laporan telah dibuat/diperbarui.
 */
export function broadcastReportsUpdated(): void {
  // 1. BroadcastChannel API (Latency ~0ms antar-tab browser di origin yang sama)
  if (typeof BroadcastChannel !== 'undefined') {
    try {
      const channel = new BroadcastChannel(REPORTS_CHANNEL_NAME);
      const msg: ReportSyncMessage = {
        type: 'REPORTS_CHANGED',
        timestamp: Date.now(),
      };
      channel.postMessage(msg);
      channel.close();
    } catch {
      // Abaikan jika env tidak mendukung BroadcastChannel
    }
  }

  // 2. StorageEvent Fallback (Bekerja antar-tab di semua peramban)
  try {
    localStorage.setItem(REPORTS_STORAGE_KEY, Date.now().toString());
  } catch {
    // Abaikan jika localStorage diblokir
  }
}

/**
 * Berlangganan (subscribe) terhadap event pembaruan laporan dari tab/jendela lain.
 * Mengembalikan fungsi cleanup (unsubscribe) saat unmount.
 */
export function subscribeToReportsSync(onUpdate: () => void): () => void {
  let channel: BroadcastChannel | null = null;

  if (typeof BroadcastChannel !== 'undefined') {
    try {
      channel = new BroadcastChannel(REPORTS_CHANNEL_NAME);
      channel.onmessage = (event: MessageEvent<ReportSyncMessage>) => {
        if (event?.data?.type === 'REPORTS_CHANGED') {
          onUpdate();
        }
      };
    } catch {
      // fallback to storage event
    }
  }

  const handleStorageEvent = (e: StorageEvent) => {
    if (e.key === REPORTS_STORAGE_KEY) {
      onUpdate();
    }
  };

  window.addEventListener('storage', handleStorageEvent);

  return () => {
    if (channel) {
      try {
        channel.close();
      } catch {
        // ignore
      }
    }
    window.removeEventListener('storage', handleStorageEvent);
  };
}

