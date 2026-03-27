import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Play, Square, Pause, Home, Scissors, RefreshCw, Lock, Unlock, 
  CloudRain, Zap, Clock, Send, ShieldAlert, CheckCircle2, XCircle, 
  Battery, Wifi, Activity, Database, AlertTriangle, Compass
} from 'lucide-react';
import { socket } from '../App';

export default function MowerControl() {
  const [status, setStatus] = useState(null);
  const [schedule, setSchedule] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // States for advanced controls
  const [torque, setTorque] = useState(0);
  const [rainDelay, setRainDelay] = useState(0);
  const [timeExtension, setTimeExtension] = useState(0);
  const [targetZone, setTargetZone] = useState(0);
  
  // State for raw json
  const [rawJson, setRawJson] = useState('{"cmd": 1}');
  const [commandHistory, setCommandHistory] = useState([]);
  
  // State for autopilot
  const [autopilot, setAutopilot] = useState(true);

  // State for raw data
  const [rawData, setRawData] = useState(null);

  const fetchStatus = async () => {
    try {
      const res = await axios.get('/api/mower/status');
      setStatus(res.data);
      if (res.data && res.data.schedule) {
          setTimeExtension(res.data.schedule.time_extension || 0);
      }
    } catch (e) {
      console.error("Error fetching mower status", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchRawData = async () => {
      try {
          const res = await axios.get('/api/mower/raw_data');
          setRawData(res.data);
      } catch (e) {
          console.error("Error fetching raw data", e);
      }
  };

  const fetchSchedule = async () => {
    try {
      const res = await axios.get('/api/mower/schedule');
      setSchedule(res.data.schedule);
    } catch (e) {
      console.error("Error fetching schedule", e);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchSchedule();
    fetchRawData();
    const interval = setInterval(() => {
        fetchStatus();
        fetchRawData();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const sendCommand = async (cmdStr, payload = {}) => {
    try {
      const res = await axios.post('/api/mower/command', { command: cmdStr, ...payload });
      if (res.data.success) {
        addHistory(`Success: ${cmdStr}`);
        setTimeout(fetchStatus, 2000);
      } else {
        addHistory(`Error: ${res.data.error}`);
      }
    } catch (e) {
      addHistory(`Failed: ${cmdStr}`);
    }
  };

  const sendRawJson = async () => {
    try {
      JSON.parse(rawJson); // Verify valid JSON
      sendCommand('raw', { data: rawJson });
    } catch (e) {
      alert("Invalid JSON");
    }
  };

  const toggleAutopilot = async () => {
    try {
      const res = await axios.post('/api/mower/autopilot', { enabled: !autopilot });
      if (res.data.success) {
        setAutopilot(res.data.autopilot);
      }
    } catch (e) {
      console.error("Toggle autopilot failed");
    }
  };

  const addHistory = (msg) => {
    setCommandHistory(prev => [msg, ...prev].slice(0, 10));
  };

  if (loading) {
    return <div className="glass-panel" style={{padding: 40, textAlign: 'center'}}><RefreshCw className="spinner" /></div>
  }

  if (!status || status.error) {
    return (
        <div className="dashboard-grid">
            <div className="glass-card" style={{gridColumn: '1 / -1'}}>
                <AlertTriangle color="#ff7b72" size={32} />
                <h3>Keine Verbindung zur Worx Cloud</h3>
                <p>{status?.error || 'Mäher-Status konnte nicht geladen werden. Bitte API überprüfen.'}</p>
                <button className="btn btn-primary mt-3" onClick={fetchStatus}>Erneut versuchen</button>
            </div>
        </div>
    );
  }

  const { battery, orientation, statistics, rainsensor } = status;

  return (
    <div className="dashboard-grid">
      
      {/* 1. Status Panel */}
      <div className="glass-card">
        <h3 className="flex-between mb-4">
          <span><Activity size={20} className="text-primary mr-2" /> Mäher Status</span>
          <span className={`badge ${status.online ? 'success' : 'danger'}`}>
            {status.online ? 'Online' : 'Offline'}
          </span>
        </h3>
        
        <div className="flex-column gap-3">
            <div className="status-row">
                <span className="text-muted">Status:</span>
                <span className={`badge ${status.status_category === 'error' ? 'danger' : 'info'}`}>
                    {status.status_text}
                </span>
            </div>
            
            {status.error_text && (
                <div className="status-row">
                    <span className="text-muted text-danger">Fehler:</span>
                    <strong className="text-danger">{status.error_text}</strong>
                </div>
            )}
            
            <div className="status-row">
                <span className="text-muted flex-center gap-2"><Battery size={16}/> Batterie:</span>
                <div className="flex-center gap-2">
                    <div style={{width: 100, height: 8, background: 'rgba(255,255,255,0.1)', borderRadius: 4, overflow: 'hidden'}}>
                        <div style={{width: `${battery?.percent || 0}%`, height: '100%', background: battery?.percent > 20 ? '#3fb950' : '#ff7b72'}} />
                    </div>
                    <span>{battery?.percent || 0}%</span>
                </div>
            </div>
            {battery && (
                <div className="status-row text-small text-muted">
                    Details: {battery.voltage}V | {battery.temperature}°C | Zykl: {battery.cycles?.total || 0}
                </div>
            )}
            
            <div className="status-row">
                <span className="text-muted flex-center gap-2"><Wifi size={16}/> WLAN (RSSI):</span>
                <span>{status.rssi || 0} dBm</span>
            </div>
            
            <div className="status-row">
                <span className="text-muted">Gesperrt:</span>
                {status.locked ? <Lock className="text-warning" size={16}/> : <Unlock className="text-success" size={16}/>}
            </div>
            
            <div className="status-row text-small text-muted mt-2">
                Letztes Update: {status.last_update}
            </div>
        </div>
      </div>
      
      {/* 2. Control Buttons */}
      <div className="glass-card">
        <h3 className="mb-4">Schnellsteuerung</h3>
        
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10}}>
            <button className="btn btn-success" onClick={() => sendCommand('start')} disabled={!status.online}>
                <Play size={18}/> Start
            </button>
            <button className="btn" style={{background: 'rgba(255,165,0,0.2)', color: 'orange'}} onClick={() => sendCommand('pause')} disabled={!status.online}>
                <Pause size={18}/> Pause
            </button>
            <button className="btn btn-primary" onClick={() => sendCommand('home')} disabled={!status.online}>
                <Home size={18}/> Home
            </button>
            <button className="btn btn-danger" onClick={() => sendCommand('stop')} disabled={!status.online}>
                <Square size={18}/> Stop
            </button>
            <button className="btn" style={{background: 'rgba(47, 129, 247, 0.2)', color: '#58a6ff'}} onClick={() => sendCommand('edgecut')} disabled={!status.online}>
                <Scissors size={18}/> Kantenschnitt
            </button>
            <button className="btn btn-danger" style={{opacity: 0.8}} onClick={() => sendCommand('safehome')} disabled={!status.online} title="Home ohne Messer">
                <ShieldAlert size={18}/> Safe Home
            </button>
            <button className="btn text-muted" style={{gridColumn: '1 / -1'}} onClick={() => sendCommand('restart')} disabled={!status.online}>
                <RefreshCw size={18}/> Mäher neu starten
            </button>
        </div>
      </div>
      
      {/* 3. IMU & Sensorfusion */}
      <div className="glass-card">
          <h3 className="flex-between mb-4">
              <span><Compass size={20} className="mr-2" /> IMU Sensor</span>
          </h3>
          <div className="flex-center" style={{flexDirection: 'column', gap: 20}}>
            <div style={{
                width: 120, height: 120, 
                borderRadius: '50%', 
                border: '4px solid rgba(255,255,255,0.1)',
                position: 'relative',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
                {/* Simple compass representation utilizing Yaw */}
                <div style={{
                    position: 'absolute', 
                    width: 4, height: 60, 
                    background: '#ff7b72', 
                    top: 10,
                    transformOrigin: 'bottom center',
                    transform: `rotate(${orientation?.yaw || 0}deg)`
                }} />
                <div style={{fontWeight: 'bold', fontSize: 24}}>{orientation?.yaw?.toFixed(0) || 0}°</div>
            </div>
            <div style={{display: 'flex', gap: 20, width: '100%', justifyContent: 'space-around'}}>
                <div className="text-center">
                    <div className="text-muted text-small">Pitch</div>
                    <strong>{orientation?.pitch?.toFixed(1) || 0}°</strong>
                </div>
                <div className="text-center">
                    <div className="text-muted text-small">Roll</div>
                    <strong>{orientation?.roll?.toFixed(1) || 0}°</strong>
                </div>
            </div>
            
            {rainsensor && (
                 <div className="status-row w-100" style={{marginTop: 10, borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 10}}>
                    <span className="text-muted"><CloudRain size={16}/> Regen-Delay:</span>
                    <span>{rainsensor.remaining || 0} min {rainsensor.triggered ? '(Aktiv)' : ''}</span>
                 </div>
            )}
          </div>
      </div>
      
      {/* 4. Erweiterte Settings */}
      <div className="glass-card" style={{gridColumn: '1 / -1', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20}}>
          <div>
            <h4 className="mb-3">Erweiterte Steuerung</h4>
            <div className="status-row mb-2">
                <span>Mäher Sperren (Lock):</span>
                <button className={`btn ${status.locked ? 'btn-danger' : 'btn-success'}`} onClick={() => sendCommand('lock', { state: !status.locked })} style={{padding: '4px 12px'}}>
                    {status.locked ? 'Entsperren' : 'Sperren'}
                </button>
            </div>
            <div className="flex-column gap-2 mb-3">
                <label className="text-small text-muted">Drehmoment (Torque): {torque}%</label>
                <div className="flex-center gap-2">
                    <input type="range" min="-50" max="50" value={torque} onChange={e => setTorque(parseInt(e.target.value))} className="w-100" />
                    <button className="btn btn-primary" onClick={() => sendCommand('torque', {value: torque})} style={{padding: '4px 8px'}}>Set</button>
                </div>
            </div>
            <div className="flex-column gap-2 mb-3">
                <label className="text-small text-muted">Regenverzögerung (Minuten):</label>
                <div className="flex-center gap-2">
                    <input type="number" className="form-control" style={{background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff'}} value={rainDelay} onChange={e => setRainDelay(parseInt(e.target.value))} />
                    <button className="btn btn-primary" onClick={() => sendCommand('raindelay', {value: rainDelay})}>Set</button>
                </div>
            </div>
          </div>
          
          <div>
            <h4 className="mb-3">Zonen & Zeitplan Option</h4>
            <div className="flex-column gap-2 mb-3">
                <label className="text-small text-muted">Zone anfahren (0-3):</label>
                <div className="flex-center gap-2">
                    <select className="form-control" style={{background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff'}} value={targetZone} onChange={e => setTargetZone(parseInt(e.target.value))}>
                        {[0,1,2,3].map(z => <option key={z} value={z}>Zone {z+1}</option>)}
                    </select>
                    <button className="btn btn-primary" onClick={() => sendCommand('setzone', {zone: targetZone})}>Go</button>
                </div>
            </div>
            <div className="flex-column gap-2 mb-3">
                <label className="text-small text-muted">Zeitplan Anpassung (%): {timeExtension}%</label>
                <div className="flex-center gap-2">
                    <input type="range" min="-100" max="100" step="10" value={timeExtension} onChange={e => setTimeExtension(parseInt(e.target.value))} className="w-100" />
                    <button className="btn btn-primary" onClick={() => sendCommand('time_extension', {value: timeExtension})} style={{padding: '4px 8px'}}>Set</button>
                </div>
            </div>
            
             <div className="flex-between" style={{borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: 10}}>
                <span className="text-muted text-small">Zeitplan aktiv:</span>
                <button className="btn" style={{padding: '4px 12px', background: 'rgba(255,255,255,0.1)'}} onClick={() => sendCommand('toggle_schedule', {enabled: !status.schedule?.active})}>
                    {status.schedule?.active ? 'Deaktivieren' : 'Aktivieren'}
                </button>
            </div>
          </div>
          
          
          <div>
            <h4 className="mb-3">Aufnahme Autopilot</h4>
            <p className="text-small text-muted" style={{minHeight: 40}}>
                Startet und stoppt die GPS-Aufnahme auf dem Pi basierend auf dem Status der Worx-Cloud.
            </p>
             <div className="status-row">
                 <span>Autopilot Status:</span>
                 <button className={`btn ${autopilot ? 'btn-success' : 'btn-danger'}`} onClick={toggleAutopilot}>
                     {autopilot ? 'Eingeschaltet' : 'Ausgeschaltet'}
                 </button>
             </div>
             
             <div className="mt-4">
                 <h4 className="text-small text-muted mb-2">Statistiken Laufzeit</h4>
                 <div className="status-row text-small">
                     <span>Distanz gefahren:</span>
                     <span>{(statistics?.distance / 1000).toFixed(1) || 0} km</span>
                 </div>
                 <div className="status-row text-small">
                     <span>Zeit Klingen an:</span>
                     <span>{(statistics?.worktime_blades_on / 60).toFixed(1) || 0} h</span>
                 </div>
             </div>
          </div>
      </div>
      
      {/* 5. Expert Mode - JSON Commands & Log */}
      <div className="glass-card" style={{gridColumn: '1 / -1'}}>
          <h3 className="flex-between mb-4">
              <span><Database size={20} className="mr-2 text-warning" /> Expert: JSON Command</span>
          </h3>
          <div className="flex-center gap-3">
              <input 
                type="text" 
                className="form-control" 
                style={{background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', color: '#0f0', fontFamily: 'monospace', flex: 1}}
                value={rawJson}
                onChange={e => setRawJson(e.target.value)}
              />
              <button className="btn" style={{background: '#ff7b72', color: '#fff'}} onClick={sendRawJson}>
                  <Send size={16}/> Senden
              </button>
          </div>
          
          <div className="mt-3">
            <h4 className="text-small text-muted mb-2">Verlauf</h4>
            <div style={{background: 'rgba(0,0,0,0.2)', padding: 10, borderRadius: 5, fontFamily: 'monospace', fontSize: 12, minHeight: 60}}>
                {commandHistory.length === 0 && <span className="text-muted">Keine Befehle gesendet</span>}
                {commandHistory.map((cmd, i) => (
                    <div key={i} style={{color: cmd.startsWith('Success') ? '#3fb950' : '#ff7b72'}}>
                        &gt; {cmd}
                    </div>
                ))}
            </div>
          </div>
      </div>

      {/* 6. Raw MQTT Monitor */}
      <div className="glass-card" style={{gridColumn: '1 / -1'}}>
          <h3 className="flex-between mb-4">
              <span><Activity size={20} className="mr-2 text-info" /> Raw MQTT Monitor (dat / cfg)</span>
              <button className="btn btn-primary" style={{padding: '4px 8px', fontSize: 12}} onClick={fetchRawData}>Aktualisieren</button>
          </h3>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20}}>
              <div>
                  <h4 className="text-small text-muted mb-2">Echtzeit (dat)</h4>
                  <pre style={{background: 'rgba(0,0,0,0.3)', padding: 15, borderRadius: 5, color: '#a5d6ff', fontSize: 12, overflowX: 'auto', maxHeight: 400}}>
                      {rawData?.dat ? JSON.stringify(rawData.dat, null, 2) : 'Warte auf Daten...'}
                  </pre>
              </div>
              <div>
                  <h4 className="text-small text-muted mb-2">Konfiguration (cfg)</h4>
                  <pre style={{background: 'rgba(0,0,0,0.3)', padding: 15, borderRadius: 5, color: '#7ee787', fontSize: 12, overflowX: 'auto', maxHeight: 400}}>
                      {rawData?.cfg ? JSON.stringify(rawData.cfg, null, 2) : 'Warte auf Daten...'}
                  </pre>
              </div>
          </div>
      </div>

    </div>
  );
}
