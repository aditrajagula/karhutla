export type DataSourceMode = 'live' | 'snapshot';

export interface SystemStatus {
  apiConfigured: boolean;
  activeMode: DataSourceMode;
  lastSyncUtc: string | null;
  snapshotPath: string;
  disclaimer: string;
}
