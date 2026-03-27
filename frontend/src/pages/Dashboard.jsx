import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Play, Square, Activity, Satellite, MapPin, Cpu, ExternalLink, 
  RefreshCw, Navigation, Home, Pause, Download, Trash, Power 
} from 'lucide-react';
import { socket, API_URL } from '../App';
import LiveMapWidget from '../components/LiveMapWidget';

export default function Dashboard() {
  const [data, setData] = useState({
    mower: {},
    system: {},
    pi: {},
    heatmaps: [],
    currentHeatmap: null,
    simulator: { running: false, exists: false }
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
        currentHeatmap: heatmapsRes.data.current_heatmap,
        simulator: { running: false, exists: false } // Will fetch separately
      }));
      fetchSimStatus();
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

  const sendMowerCommand = async (cmdStr) => {
    try {
      await axios.post('/api/mower/command', { command: cmdStr });
    } catch(err) {
      console.error(err);
    }
  };

  const fetchSimStatus = async () => {
    try {
      const res = await axios.get('/api/simulator/status');
      setData(prev => ({ ...prev, simulator: res.data }));
    } catch(err) { console.error(err); }
  };

  const toggleSimulator = async () => {
    try {
      const res = await axios.post('/api/simulator/toggle');
      setData(prev => ({ ...prev, simulator: { ...prev.simulator, running: res.data.running } }));
      setTimeout(fetchStatus, 500); // Re-fetch status to see simulator activity
    } catch(err) { console.error(err); }
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
          <div className="flex-center" style={{gap: 8}}>
            {mower.is_simulated && (
              <span className="badge danger" style={{animation: 'pulse 2s infinite'}}>SIMULATION</span>
            )}
            <span className={`badge ${mower.is_recording ? 'success' : 'secondary'}`}>
              {mower.is_recording ? 'Aufzeichnung Aktiv' : 'Gestoppt'}
            </span>
          </div>
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

          <div className="status-row" style={{borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: 8, marginTop: 4}}>
            <span className="text-muted flex-between" style={{gap:8}}>IMU Sensoren:</span>
            <div className="flex-center" style={{gap: 6}}>
              <span title="Pitch (Neigung)" className="badge" style={{background: 'rgba(255,255,255,0.1)'}}>P: {mower.imu_pitch || 0}°</span>
              <span title="Roll (Rollen)" className="badge" style={{background: 'rgba(255,255,255,0.1)'}}>R: {mower.imu_roll || 0}°</span>
              <span title="Yaw (Gieren)" className="badge" style={{background: 'rgba(255,255,255,0.1)'}}>Y: {mower.imu_yaw || 0}°</span>
            </div>
          </div>
          <div className="status-row">
            <span className="text-muted flex-between" style={{gap:8}}>Sensor Fusion:</span>
            <span className={`badge ${mower.imu_yaw !== undefined && mower.imu_yaw !== 0 ? 'success' : 'warning'}`}>
              {mower.imu_yaw !== undefined && mower.imu_yaw !== 0 ? 'Aktiv (GPS + IMU)' : 'Nur GPS'}
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
            className="btn mt-2 mb-2" style={{background: 'rgba(47, 129, 247, 0.2)', color: '#58a6ff'}}
            onClick={() => sendCommand('generate_heatmaps')}
          >
            <RefreshCw size={18} /> Heatmaps generieren
          </button>

          <div style={{borderTop: '1px solid rgba(255,255,255,0.1)', margin: '10px 0'}}></div>
          
          <span className="text-small text-muted">Mäher Steuerung:</span>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8}}>
              <button className="btn btn-success" onClick={() => sendMowerCommand('start')}>
                  <Play size={16}/> Start
              </button>
              <button className="btn" style={{background: 'rgba(255,165,0,0.2)', color: 'orange'}} onClick={() => sendMowerCommand('pause')}>
                  <Pause size={16}/> Pause
              </button>
              <button className="btn btn-primary" onClick={() => sendMowerCommand('home')}>
                  <Home size={16}/> Home
              </button>
              <button className="btn btn-danger" onClick={() => sendMowerCommand('stop')}>
                  <Square size={16}/> Stop
              </button>
          </div>
        </div>
      </div>

      {/* Simulator Control Panel */}
      <div className={`glass-card ${data.simulator.running ? 'border-primary' : ''}`}>
        <h3 className="flex-between mb-4" style={{marginBottom: 20}}>
          <span className="flex-center" style={{gap: 8}}><Cpu size={20} className={data.simulator.running ? 'text-primary' : ''} /> Simulator</span>
          <span className={`badge ${data.simulator.running ? 'success' : 'secondary'}`}>
            {data.simulator.running ? 'Simuliert...' : 'Inaktiv'}
          </span>
        </h3>
        
        <p className="text-small text-muted mb-4" style={{minHeight: 40}}>
          {data.simulator.running 
            ? 'Virtueller Mäher fährt nach dem Chaos-Prinzip innerhalb der Geofences.' 
            : 'Simuliert GPS-Daten via MQTT für Testzwecke ohne echte Hardware.'}
        </p>

        <div className="flex-column gap-3">
          <button 
            className={`btn ${data.simulator.running ? 'btn-danger' : 'btn-primary'}`}
            onClick={toggleSimulator}
          >
            {data.simulator.running ? <Square size={18} /> : <Play size={18} />}
            {data.simulator.running ? ' Simulation beenden' : ' Simulation starten'}
          </button>
          
          {data.simulator.running && (
            <div className="status-row text-small mt-2" style={{opacity: 0.8}}>
               <Navigation size={14}/> {data.simulator.lat?.toFixed(6)}, {data.simulator.lon?.toFixed(6)}
            </div>
          )}
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

        {/* Pi Zero Remote Control */}
        <div style={{borderTop: '1px solid rgba(255,255,255,0.1)', marginTop: 15, paddingTop: 15}}>
          <span className="text-small text-muted mb-2 block" style={{display: 'block', marginBottom: 10, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em'}}>Pi Zero Remote Control:</span>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8}}>
            <button 
              className="btn btn-small" 
              style={{background: 'rgba(56, 139, 253, 0.15)', color: '#58a6ff', fontSize: '0.75rem', padding: '6px 4px'}}
              onClick={() => sendCommand('git_pull')}
              title="Aktualisiert den Code vom GitHub Repository"
            >
              <Download size={14} style={{marginRight: 4}}/> Git Pull
            </button>
            <button 
              className="btn btn-small" 
              style={{background: 'rgba(56, 139, 253, 0.15)', color: '#58a6ff', fontSize: '0.75rem', padding: '6px 4px'}}
              onClick={() => sendCommand('restart_service')}
              title="Startet den Worx GPS Dienst neu"
            >
              <RefreshCw size={14} style={{marginRight: 4}}/> Restart
            </button>
            <button 
              className="btn btn-small" 
              style={{background: 'rgba(215, 58, 73, 0.15)', color: '#f85149', fontSize: '0.75rem', padding: '6px 4px'}}
              onClick={() => sendCommand('wipe_buffer')}
              title="Löscht den lokalen GPS-Puffer"
            >
              <Trash size={14} style={{marginRight: 4}}/> Wipe
            </button>
            <button 
              className="btn btn-small" 
              style={{background: 'rgba(215, 58, 73, 0.15)', color: '#f85149', fontSize: '0.75rem', padding: '6px 4px'}}
              onClick={() => sendCommand('reboot_pi')}
              title="Startet den gesamten Raspberry Pi neu"
            >
              <Power size={14} style={{marginRight: 4}}/> Reboot
            </button>
          </div>
        </div>
      </div>

      {/* Maps Container - Grid mit 2 Spalten */}
      <div style={{gridColumn: '1 / -1', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '20px'}}>
        {/* Live Map Preview */}
        <div className="glass-card">
          <h3 className="flex-between" style={{marginBottom: 20}}>
            <span><Navigation size={20} /> Live Map</span>
            <button className="btn" onClick={() => window.location.href='/live'} style={{padding: '6px 12px', fontSize: 13, background: 'rgba(255,255,255,0.1)'}}>
              Vollbild <ExternalLink size={14}/>
            </button>
          </h3>
          <div className="map-frame" style={{height: '400px', border: 'none', background: 'transparent'}}>
            <LiveMapWidget socket={socket} height="100%" />
          </div>
        </div>

        {/* Heatmap Preview */}
        <div className="glass-card">
          <h3 className="flex-between" style={{marginBottom: 20}}>
            <span><Activity size={20} /> Aktuelle Heatmap</span>
            <button className="btn" onClick={() => window.location.href='/maps'} style={{padding: '6px 12px', fontSize: 13, background: 'rgba(255,255,255,0.1)'}}>
              Vollbild <ExternalLink size={14}/>
            </button>
          </h3>
          <div className="map-frame" style={{height: '400px'}}>
            {currentHeatmap ? (
                <iframe src={`${API_URL}${currentHeatmap}`} style={{width: '100%', height: '100%', border: 'none'}} />
            ) : (
              <div className="flex-between" style={{height: '100%', justifyContent: 'center', color: '#888'}}>
                No heatmap found or generated yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
