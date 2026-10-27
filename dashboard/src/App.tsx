import { useState, useEffect } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { Activity, AlertTriangle, Wifi, WifiOff, RefreshCw } from 'lucide-react';
import type { TelemetryPayload } from './types/telemetry';

// Fixture dự phòng khi chưa nối được Backend
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

export function App() {
  const [data, setData] = useState<TelemetryPayload | null>(null);
  const [historyPackets, setHistoryPackets] = useState<TelemetryPayload[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [isStale, setIsStale] = useState<boolean>(false);
  const [isLiveApi, setIsLiveApi] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Hàm fetch lịch sử 15 phút khi mới mở trang
  const fetchHistory = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/devices/${DEVICE_ID}/history`, {
        headers: { 'X-Read-Key': READ_KEY },
      });
      if (response.ok) {
        const result = await response.json();
        const packets = Array.isArray(result) ? result : (result.items || result.packets || []);
        setHistoryPackets(packets.slice(-90));
      }
    } catch (err) {
      console.error("Failed to load history", err);
    }
  };

  // Hàm fetch dữ liệu từ Backend API
  const fetchLatestTelemetry = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/devices/${DEVICE_ID}/latest`, {
        headers: {
          'X-Read-Key': READ_KEY,
        },
      });

      if (!response.ok) {
        // Nếu trả về 404 nghĩa là API vẫn sống, chỉ là thiết bị chưa có dữ liệu.
        if (response.status === 404) {
          setData(null);
          setIsLiveApi(true);
          setIsStale(true);
          setApiError(null);
          return;
        }

        throw new Error(`API Error: ${response.status}`);
      }

      const result = await response.json();

      if (result.packet) {
        setData(result.packet);
        if (result.packet.measured_at) {
          setLastUpdated(new Date(result.packet.measured_at));
        }

        const isDataStale = result.freshness ? result.freshness.status !== 'fresh' : false;
        setIsStale(isDataStale);

        setIsLiveApi(true);
        setApiError(null);

        // Đẩy gói dữ liệu mới vào biểu đồ một cách an toàn
        setHistoryPackets(prev => {
          if (prev.some(p => p.sequence === result.packet.sequence)) return prev;
          return [...prev, result.packet].slice(-90);
        });
      }
    } catch (err) {
      // Khi không kết nối được API thật, giữ lại trạng thái cũ và báo Stale/Offline
      setIsLiveApi(false);
      setApiError(err instanceof Error ? err.message : 'Failed to connect to backend API');

      if (typeof MOCK_FIXTURE !== 'undefined') {
        setData(MOCK_FIXTURE);
        setHistoryPackets([MOCK_FIXTURE]);
      }
      setIsStale(true);
    }
  };

  // Tự động làm mới mỗi 5 giây
  useEffect(() => {
    let isCancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const startPolling = async () => {
      await fetchHistory(); // Lấy lịch sử lần đầu tiên

      const poll = async () => {
        if (isCancelled) return;
        await fetchLatestTelemetry();
        // Chờ request trước xong hoàn toàn mới đếm 5s tiếp theo
        timer = setTimeout(poll, 5000);
      };

      poll();
    };

    startPolling();

    return () => {
      isCancelled = true;
      clearTimeout(timer);
    };
  }, []);

  // Kiểm tra stale (> 30s không nhận số đo mới)
  useEffect(() => {
    const checkStaleInterval = setInterval(() => {
      const secondsPassed = (new Date().getTime() - lastUpdated.getTime()) / 1000;
      if (secondsPassed > 30) {
        setIsStale(true);
      }
    }, 1000);
    return () => clearInterval(checkStaleInterval);
  }, [lastUpdated]);

  // Gom toàn bộ mảng historyPackets thành mảng chart dài liên tục
  const chartData = historyPackets.flatMap((packet, packetIdx) =>
    packet.median_p2p.map((val, idx) => ({
      sampleIndex: (packetIdx * 10) + idx + 1,
      median: val,
      peak: packet.peak_p2p[idx] ?? null,
      flag: packet.quality_flags[idx]
    }))
  );

  const latestMedian = data?.median_p2p[data.median_p2p.length - 1] ?? 'N/A';
  const latestPeak = data?.peak_p2p[data.peak_p2p.length - 1] ?? 'N/A';

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
            onClick={fetchLatestTelemetry}
            style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', cursor: 'pointer', border: '1px solid #cbd5e1', borderRadius: '6px', backgroundColor: '#fff' }}
          >
            <RefreshCw size={14} /> Refresh Now
          </button>
        </div>

        <div style={{ width: '100%', height: '320px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 30, left: 20, bottom: 25 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="sampleIndex" label={{ value: 'Sample Window', position: 'insideBottom', offset: -15 }} />
              <YAxis label={{ value: 'Relative ADC', angle: -90, position: 'insideLeft', offset: -8 }} />
              <Tooltip />
              <Line type="monotone" dataKey="median" stroke="#2563eb" name="Median P2P" connectNulls={false} strokeWidth={2} />
              <Line type="monotone" dataKey="peak" stroke="#dc2626" name="Peak P2P" connectNulls={false} strokeWidth={1.5} strokeDasharray="3 3" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default App;