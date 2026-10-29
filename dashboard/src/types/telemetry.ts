export type TimeSyncStatus = 'synced' | 'unsynced' | 'monotonic';

export interface TelemetryPayload {
  schema_version: 'v1';
  device_id: string;
  boot_id: string;
  sequence: number;
  measured_at: string;
  timezone: string;
  time_sync_status: TimeSyncStatus;
  median_p2p: (number | null)[];
  peak_p2p: (number | null)[];
  quality_flags: string[];
}

export interface LatestDeviceResponse {
  device_id: string;
  latest: TelemetryPayload | null;
  last_received_at: string | null;
  is_stale: boolean;
}