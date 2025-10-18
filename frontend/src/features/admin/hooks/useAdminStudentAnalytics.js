import { useEffect, useRef, useState } from 'react';

const useAdminStudentAnalytics = (studentId) => {
  const [data, setData] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!studentId) return;
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host;
    const wsUrl = `${protocol}://${host}/ws/admin/student_analytics/${studentId}/`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => { setConnected(true) };
    ws.onmessage = (evt) => {
      try {
        const payload = JSON.parse(evt.data);
        if (payload.type === 'analytics.update') {
          setData(payload.data);
        }
      } catch (err) { console.error('WS parse error', err) }
    };
    ws.onclose = () => { setConnected(false); }
    ws.onerror = (e) => { console.error('WS error', e); }

    return () => { ws.close(); }
  }, [studentId]);

  const send = (msg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }

  return { data, connected, send };
}

export default useAdminStudentAnalytics;
