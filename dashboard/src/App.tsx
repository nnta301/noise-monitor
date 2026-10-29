import { useState, useEffect, useRef, useCallback } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { Activity, AlertTriangle, Wifi, WifiOff, RefreshCw } from 'lucide-react';
import type { TelemetryPayload } from './types/telemetry';

const MOCK_FIXTURE: TelemetryPayload = {
  schema_version: 'v1',
  device_id: 'esp32-sleep-monitor-01',
  boot_id: 'b82a1012-4c2d-419b',
  sequence: 42,
  measured_at: new Date().toISOString(),
  timezone: 'Asia/Ho_Chi_Minh',
  time_sync_status: 'synced',
  median_p2p: [42, 45, 41, 40, null, 43, 44, 48, 50, 46],
  peak_p2p: [55, 60, 52, 50, null, 58, 62, 70, 75, 65],
  quality_flags: ['ok', 'ok', 'ok', 'ok', 'missing_sample', 'ok', 'ok', 'ok', 'ok', 'ok']
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const DEVICE_ID = import.meta.env.VITE_DEVICE_ID || 'esp32-sleep-monitor-01';
const READ_KEY = import.meta.env.VITE_READ_KEY || '';

// Đưa hàm mergePackets ra ngoài component để đảm bảo tính thuần khiết
const mergePackets = (prev: TelemetryPayload[], incoming: TelemetryPayload[]) => {
  const combined = [...prev, ...incoming];
  const unique = Array.from(new Map(combined.map(p => {
    const key = `${p.boot_id}-${(p as unknown as { seq?: number; sequence?: number }).seq ?? p.sequence}`;
    return [key, p];
  })).values());

  unique.sort((a, b) => {
    const timeA = a.measured_at ? new Date(a.measured_at).getTime() : 0;
    const timeB = b.measured_at ? new Date(b.measured_at).getTime() : 0;
    return timeA - timeB;
  });
  return unique.slice(-90);
};

export function App() {
  const [data, setData] = useState<TelemetryPayload | null>(null);
  const [historyPackets, setHistoryPackets] = useState<TelemetryPayload[]>([]);
  const [nowTime, setNowTime] = useState<number>(() => Date.now());
  const [lastUpdated, setLastUpdated] = useState<Date>(() => new Date());
  const [isStale, setIsStale] = useState<boolean>(false);
  const [isLiveApi, setIsLiveApi] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const liveGenRef = useRef<number>(0);
  const historyGenRef = useRef<number>(0);

  const isHistoryInFlightRef = useRef<boolean>(false);
  const needsHistoryRef = useRef<boolean>(true);
  const lastPollTimeRef = useRef<number>(0);

  // Dùng useCallback để thỏa mãn quy tắc react-hooks/exhaustive-deps
  const fetchHistory = useCallback(async (gen: number) => {
    if (isHistoryInFlightRef.current && gen === historyGenRef.current) return;
    isHistoryInFlightRef.current = true;

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/devices/${DEVICE_ID}/history?t=${Date.now()}`, {
        headers: { 'X-Read-Key': READ_KEY },
        cache: 'no-store'
      });

      if (!response.ok) {
        throw new Error(`HTTP Error ${response.status}`);
      }

      const result = await response.json();

      if (gen !== historyGenRef.current) return;

      const items = Array.isArray(result) ? result : (result.items || result.packets || []);

      // Fix lỗi any bằng cách khai báo kiểu giao cắt rõ ràng
      const normalizedPackets: TelemetryPayload[] = items.map(
        (item: { packet?: TelemetryPayload } & TelemetryPayload) => item.packet || item
      ).reverse();

      if (normalizedPackets.length > 0) {
        setHistoryPackets(prev => mergePackets(prev, normalizedPackets));
      }

      setHistoryError(null);
      needsHistoryRef.current = false;
    } catch (err) {
      if (gen !== historyGenRef.current) return;
      setHistoryError(err instanceof Error ? err.message : 'Failed to load history');
      needsHistoryRef.current = true;
    } finally {
      if (gen === historyGenRef.current) {
        isHistoryInFlightRef.current = false;
      }
    }
  }, []);

  const fetchLatestTelemetry = useCallback(async (gen: number) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/devices/${DEVICE_ID}/latest?t=${Date.now()}`, {
        headers: { 'X-Read-Key': READ_KEY },
        cache: 'no-store'
      });

      if (!response.ok) {
        if (response.status === 404) {
          if (gen !== liveGenRef.current) return;
          setData(null);
          setIsLiveApi(true);
          setIsStale(true);
          setApiError(null);
          return;
        }
        throw new Error(`API Error: ${response.status}`);
      }

      const result = await response.json();
      const packetData: TelemetryPayload | null = result.packet || result.latest_measurement || (result.median_p2p ? result : null);

      if (gen !== liveGenRef.current) return;

      if (packetData) {
        setData(packetData);
        if (packetData.measured_at) {
          setLastUpdated(new Date(packetData.measured_at));
        }

        const isDataStale = result.freshness ? result.freshness.status !== 'fresh' : false;
        setIsStale(isDataStale);
        setIsLiveApi(true);
        setApiError(null);
        setHistoryPackets(prev => mergePackets(prev, [packetData]));
      }
    } catch (err) {
      if (gen !== liveGenRef.current) return;
      setIsLiveApi(false);
      setApiError(err instanceof Error ? err.message : 'Failed to connect to backend API');

      if (typeof MOCK_FIXTURE !== 'undefined') {
        setData(MOCK_FIXTURE);
        setHistoryPackets([MOCK_FIXTURE]);
      }
      setIsStale(true);
    }
  }, []);

  const handleManualRefresh = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);

    const nextLiveGen = ++liveGenRef.current;
    const nextHistoryGen = ++historyGenRef.current;

    try {
      await Promise.all([fetchHistory(nextHistoryGen), fetchLatestTelemetry(nextLiveGen)]);
    } finally {
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  useEffect(() => {
    let isCancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      if (isCancelled) return;

      const now = Date.now();

      if (lastPollTimeRef.current === 0) {
        lastPollTimeRef.current = now;
      }

      const timeSinceLastPoll = now - lastPollTimeRef.current;
      if (timeSinceLastPoll > 15000) {
        needsHistoryRef.current = true;
      }
      lastPollTimeRef.current = now;

      const nextLiveGen = ++liveGenRef.current;

      if (needsHistoryRef.current && !isHistoryInFlightRef.current) {
        const nextHistoryGen = ++historyGenRef.current;
        void fetchHistory(nextHistoryGen);
      }

      await fetchLatestTelemetry(nextLiveGen);

      timer = setTimeout(poll, 5000);
    };

    poll();

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        needsHistoryRef.current = true;
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      isCancelled = true;
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [fetchHistory, fetchLatestTelemetry]);

  useEffect(() => {
    const checkStaleInterval = setInterval(() => {
      setNowTime(Date.now());
      const secondsPassed = (new Date().getTime() - lastUpdated.getTime()) / 1000;
      setIsStale(secondsPassed > 30);
    }, 1000);
    return () => clearInterval(checkStaleInterval);
  }, [lastUpdated]);

  const MAX_SAMPLES = 900;

  const getLatestSampleTime = (packets: TelemetryPayload[], fallbackTimeMs: number) => {
    if (packets.length === 0) return fallbackTimeMs;
    const last = packets[packets.length - 1];
    return last.measured_at ? new Date(last.measured_at).getTime() : fallbackTimeMs;
  };

  const latestSampleTimeMs = getLatestSampleTime(historyPackets, nowTime);
  const referenceTimeMs = isStale ? nowTime : latestSampleTimeMs;

  const chartData = Array.from({ length: MAX_SAMPLES }, (_, i) => ({
    sampleIndex: i,
    median: null as number | null,
    peak: null as number | null,
    flag: 'none'
  }));

  historyPackets.forEach((packet) => {
    if (!packet.measured_at) return;
    const packetTimeMs = new Date(packet.measured_at).getTime();
    const sampleCount = packet.median_p2p?.length || 10;

    (packet.median_p2p || []).forEach((val, idx) => {
      const sampleTimeMs = packetTimeMs - (sampleCount - 1 - idx) * 1000;
      const ageInSeconds = Math.floor((referenceTimeMs - sampleTimeMs) / 1000);
      const targetIndex = (MAX_SAMPLES - 1) - ageInSeconds;

      if (targetIndex >= 0 && targetIndex < MAX_SAMPLES) {
        chartData[targetIndex] = {
          sampleIndex: targetIndex,
          median: val,
          peak: packet.peak_p2p?.[idx] ?? null,
          flag: packet.quality_flags?.[idx] ?? 'ok'
        };
      }
    });
  });

  const getLatestKPIs = (packets: TelemetryPayload[]) => {
    if (isStale || packets.length === 0) return { median: 'N/A', peak: 'N/A' };

    const lastPacket = packets[packets.length - 1];

    let medianVal: string | number = 'N/A';
    if (lastPacket.median_p2p) {
      for (let i = lastPacket.median_p2p.length - 1; i >= 0; i--) {
        if (lastPacket.median_p2p[i] !== null && lastPacket.median_p2p[i] !== undefined) {
          medianVal = lastPacket.median_p2p[i]!;
          break;
        }
      }
    }

    let peakVal: string | number = 'N/A';
    if (lastPacket.peak_p2p) {
      const validPeaks = lastPacket.peak_p2p.filter((v): v is number => v !== null && v !== undefined);
      if (validPeaks.length > 0) {
        peakVal = Math.max(...validPeaks);
      }
    }

    return { median: medianVal, peak: peakVal };
  };

  const { median: latestMedian, peak: latestPeak } = getLatestKPIs(historyPackets);

  return (
    <div style={{ padding: '24px', fontFamily: 'sans-serif', backgroundColor: '#f8fafc', minHeight: '100vh' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity color="#2563eb" /> Noise Monitoring Dashboard
          </h1>
          <span style={{ fontSize: '12px', background: isLiveApi ? '#dcfce7' : '#e0f2fe', color: isLiveApi ? '#15803d' : '#0369a1', padding: '2px 8px', borderRadius: '4px', marginTop: '4px', display: 'inline-block' }}>
            {isLiveApi ? 'Connected to Backend API' : 'Synthetic / Fixture Fallback Mode'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', borderRadius: '8px', backgroundColor: isStale ? '#fef2f2' : '#f0fdf4', border: `1px solid ${isStale ? '#fecaca' : '#bbf7d0'}` }}>
          {isStale ? <WifiOff color="#dc2626" /> : <Wifi color="#16a34a" />}
          <div>
            <div style={{ fontWeight: 'bold', color: isStale ? '#dc2626' : '#16a34a' }}>
              {isStale ? 'STALE / OFFLINE' : 'LIVE'}
            </div>
            <div style={{ fontSize: '12px', color: '#64748b' }}>
              Last update: {lastUpdated.toLocaleTimeString()}
            </div>
          </div>
        </div>
      </header>

      {historyError && (
        <div style={{ backgroundColor: '#fef2f2', borderLeft: '4px solid #ef4444', padding: '12px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle color="#ef4444" />
          <span>Failed to load signal history ({historyError}). Retrying automatically...</span>
        </div>
      )}

      {apiError && !isLiveApi && (
        <div style={{ backgroundColor: '#fff7ed', borderLeft: '4px solid #f97316', padding: '12px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle color="#f97316" />
          <span>Backend API disconnected ({apiError}). Using local mock fallback data.</span>
        </div>
      )}

      {isStale && (
        <div style={{ backgroundColor: '#fef2f2', borderLeft: '4px solid #dc2626', padding: '12px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertTriangle color="#dc2626" />
          <span>Warning: No new measurement received for over 30 seconds. System is STALE.</span>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        <div style={{ backgroundColor: '#ffffff', padding: '16px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ color: '#64748b', fontSize: '14px' }}>Device ID</div>
          <div style={{ fontSize: '18px', fontWeight: 'bold' }}>{data?.device_id || DEVICE_ID}</div>
          <div style={{ fontSize: '12px', color: '#94a3b8' }}>Boot ID: {data?.boot_id || 'N/A'}</div>
        </div>

        <div style={{ backgroundColor: '#ffffff', padding: '16px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ color: '#64748b', fontSize: '14px' }}>Latest Median Level</div>
          <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#2563eb' }}>
            {latestMedian} <span style={{ fontSize: '14px', color: '#64748b', fontWeight: 'normal' }}>Relative ADC units</span>
          </div>
        </div>

        <div style={{ backgroundColor: '#ffffff', padding: '16px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <div style={{ color: '#64748b', fontSize: '14px' }}>Latest Peak Level</div>
          <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#dc2626' }}>
            {latestPeak} <span style={{ fontSize: '14px', color: '#64748b', fontWeight: 'normal' }}>Relative ADC units</span>
          </div>
        </div>
      </div>

      <div style={{ backgroundColor: '#ffffff', padding: '20px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ margin: 0 }}>Signal History (Relative ADC Units)</h3>
          <button
            onClick={handleManualRefresh}
            disabled={isRefreshing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              cursor: isRefreshing ? 'not-allowed' : 'pointer',
              border: '1px solid #cbd5e1',
              borderRadius: '6px',
              backgroundColor: '#fff',
              opacity: isRefreshing ? 0.7 : 1,
              transition: 'all 0.2s ease'
            }}
          >
            <RefreshCw
              size={14}
              style={{
                transition: 'transform 0.5s ease',
                transform: isRefreshing ? 'rotate(360deg)' : 'none'
              }}
            />
            {isRefreshing ? 'Refreshing...' : 'Refresh Now'}
          </button>
        </div>

        <div style={{ width: '100%', height: '420px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 20, bottom: 25 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="sampleIndex"
                type="number"
                domain={[0, 899]}
                minTickGap={60}
                tickFormatter={(value) => {
                  const minsAgo = Math.round((899 - value) / 60);
                  if (minsAgo <= 0) return 'Now';
                  return `-${minsAgo}m`;
                }}
                label={{ value: 'Relative Time', position: 'insideBottom', offset: -15 }}
              />
              <YAxis
                domain={[0, 5000]}
                tickCount={6}
                label={{ value: 'Relative ADC', angle: -90, position: 'insideLeft', offset: -8 }}
              />

              <Tooltip
                labelFormatter={(value) => {
                  const valNum = typeof value === 'number' ? value : Number(value);
                  const minsAgo = Math.round((899 - valNum) / 60);
                  return minsAgo <= 0 ? 'Current Sample' : `${minsAgo}m ago`;
                }}
                formatter={(value, name) => [
                  value !== null && value !== undefined ? `${value} units` : 'N/A',
                  String(name ?? '')
                ]}
              />

              <Line type="monotone" dataKey="median" stroke="#2563eb" name="Median P2P" connectNulls={false} strokeWidth={2} dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="peak" stroke="#dc2626" name="Peak P2P" connectNulls={false} strokeWidth={1.5} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default App;