import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Play, Square, Activity, Satellite, MapPin, Cpu, ExternalLink, RefreshCw } from 'lucide-react';
import { socket } from '../App';

export default function Dashboard() {
  const [data, setData] = useState({
    mower: {},
    system: {},
    pi: {},
    heatmaps: [],
    currentHeatmap: null
  });

  const [loading, setLoading] = useState(true);

  const fetchStatus = async () => {
    try {
      const [statusRes, heatmapsRes] = await Promise.all([
        axios.get('/api/status'),
        axios.get('/api/heatmaps')
      ]);
      setData(prev => ({
        ...prev,
        mower: statusRes.data.mower || {},
        system: statusRes.data.system || {},
        pi: statusRes.data.pi || {},
        heatmaps: heatmapsRes.data.heatmaps || [],
        currentHeatmap: heatmapsRes.data.current_heatmap
      }));
    } catch(err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();

    socket.on('status_update', (msg) => {
      setData(prev => ({ ...prev, mower: msg || {} }));
    });
    socket.on('system_update', (sys) => setData(prev => ({ ...prev, system: sys || {} })));
    socket.on('pi_status_update', (piMsg) => setData(prev => ({ ...prev, pi: piMsg || {} })));

    return () => {
      socket.off('status_update');
      socket.off('system_update');
      socket.off('pi_status_update');
    }
  }, []);

  const sendCommand = async (cmd) => {
    await axios.post('/control', { command: cmd });
  };

  if (loading) {
    return <div className="glass-panel" style={{padding: 40, textAlign: 'center'}}><RefreshCw className="spinner" /></div>
  }

  const { mower, system, pi, currentHeatmap, heatmaps } = data;

  return (
    <div className="dashboard-grid">
      
      {/* Mower Status Card */}
      <div className="glass-card">
        <h3 className="flex-between mb-4" style={{marginBottom: 20}}>
          <span><Activity size={20} className="text-primary mr-2" /> Live Status</span>
          <span className={`badge ${mower.is_recording ? 'success' : 'secondary'}`}>
            {mower.is_recording ? 'Aufzeichnung Aktiv' : 'Gestoppt'}
          </span>
        </h3>

        <div className="flex-column gap-3">
          <div className="status-row">
            <span className="text-muted flex-between" style={{gap:8}}>Mäher-Status:</span>
            <span className="badge info">{mower.mower_status || 'Unbekannt'}</span>
          </div>

          <div className="status-row">
            <span className="text-muted flex-between" style={{gap:8}}><Satellite size={16}/> GPS-Fix:</span>
            <span className={`badge ${mower.satellites >= 4 ? 'success' : 'warning'}`}>
              {mower.status_text || 'Warte auf Signal...'}
            </span>
          </div>

          <div className="status-row">
            <span className="text-muted">Satelliten:</span>
            <span className={`badge ${mower.satellites >= 8 ? 'success' : mower.satellites >= 4 ? 'warning' : 'danger'}`}>
              {mower.satellites || 0}
            </span>
          </div>

          <div className="status-row">
            <span className="text-muted flex-between" style={{gap:8}}><MapPin size={16}/> Position:</span>
            <span>
              {mower.lat?.toFixed(6) || 'N/A'}, {mower.lon?.toFixed(6) || 'N/A'}
            </span>
          </div>
          
          <div className="status-row text-small text-muted mt-2">
            Zuletzt aktualisiert: {mower.last_update || '-'}
          </div>
        </div>
      </div>

      {/* Control Panel */}
      <div className="glass-card flex-column">
        <h3 style={{marginBottom: 20}}>Aktionen</h3>
        
        <div className="flex-column gap-3" style={{flex: 1}}>
          <button 
            className="btn btn-success" 
            disabled={mower.is_recording}
            onClick={() => sendCommand('start_recording')}
          >
            <Play size={18} /> Aufnahme starten
          </button>
          
          <button 
            className="btn btn-danger" 
            disabled={!mower.is_recording}
            onClick={() => sendCommand('stop_recording')}
          >
            <Square size={18} /> Aufnahme abschließen
          </button>

          <button 
            className="btn mt-4" style={{background: 'rgba(47, 129, 247, 0.2)', color: '#58a6ff'}}
            onClick={() => sendCommand('generate_heatmaps')}
          >
            <RefreshCw size={18} /> Heatmaps generieren
          </button>
        </div>
      </div>

      {/* System Stats */}
      <div className="glass-card">
        <h3 className="flex-between mb-4" style={{marginBottom: 20}}>
          <span><Cpu size={20} /> System Info</span>
        </h3>
        
        <div className="status-row">
          <span className="text-muted">Server CPU Load:</span>
          <strong>{system.cpu_load?.toFixed(1) || 0}%</strong>
        </div>
        <div className="status-row">
          <span className="text-muted">Server RAM:</span>
          <strong>{system.ram_usage?.toFixed(1) || 0}%</strong>
        </div>
        <div className="status-row">
          <span className="text-muted">Server Temp:</span>
          <strong>{system.cpu_temp ? `${system.cpu_temp.toFixed(1)}°C` : 'N/A'}</strong>
        </div>

        <div className="status-row" style={{borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 16, marginTop: 8}}>
          <span className="text-muted">Pi Zero Status (Roboter):</span>
        </div>
        <div className="status-row">
          <span className="text-muted">Temp:</span>
          <strong>{pi?.temperature ? `${pi.temperature.toFixed(1)}°C` : 'N/A'}</strong>
        </div>
        <div className="text-small text-muted mt-2">
           Pi Update: {pi?.last_update || '-'}
        </div>
      </div>

      {/* Map Preview */}
      <div className="glass-card" style={{gridColumn: '1 / -1'}}>
         <h3 className="flex-between" style={{marginBottom: 20}}>
           <span>Aktuelle Heatmap</span>
           <button className="btn" style={{padding: '6px 12px', fontSize: 13, background: 'rgba(255,255,255,0.1)'}}>
             Vollbild <ExternalLink size={14}/>
           </button>
         </h3>
         <div className="map-frame">
           {currentHeatmap ? (
              <iframe src={`http://${window.location.hostname}:5000${currentHeatmap}`} />
           ) : (
             <div className="flex-between" style={{height: '100%', justifyContent: 'center', color: '#888'}}>
               No heatmap found or generated yet.
             </div>
           )}
         </div>
      </div>
    </div>
  )
}
