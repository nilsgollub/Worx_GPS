import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, Save, Trash2, AlertTriangle, GitBranch, RotateCcw, Power, Eraser, Loader2 } from 'lucide-react';

export default function Config({ addToast }) {
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [includeGeofences, setIncludeGeofences] = useState(false);
  const [commandLoading, setCommandLoading] = useState({});

  useEffect(() => {
    axios.get('/api/config').then(res => {
      const cfg = res.data.config || {};
      const mappedCfg = { ...cfg };
      ['outlier_detection', 'dead_reckoning', 'rec_test_mode', 'heatmap_generate_png', 'debug_logging'].forEach(key => {
        if (typeof mappedCfg[key] === 'boolean') {
          mappedCfg[key] = mappedCfg[key] ? 'on' : 'off';
        }
      });
      setConfig(mappedCfg);
      setLoading(false);
    });
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setConfig(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (checked ? 'on' : 'off') : value
    }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    const formData = new FormData();
    Object.keys(config).forEach(key => {
      formData.append(key, config[key]);
    });

    try {
      const res = await axios.post('/config/save', formData);
      if (addToast) addToast('success', res.data.message || 'Einstellungen gespeichert');
    } catch(err) {
      if (addToast) addToast('error', 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const handleDatabaseReset = async () => {
    const geofenceText = includeGeofences ? ' und alle Geofences' : '';
    const warningText = `⚠️ Wirklich alle Mähsessions${geofenceText} löschen?\n\nDiese Aktion kann nicht rückgängig gemacht werden.`;
    
    if (!confirm(warningText)) return;

    setResetting(true);
    try {
      const res = await axios.post('/api/database/reset', { include_geofences: includeGeofences });
      if (addToast) addToast('success', res.data.message);
      window.location.reload();
    } catch(err) {
      const message = err.response?.data?.message || 'Fehler beim Zurücksetzen';
      if (addToast) addToast('error', message);
    } finally {
      setResetting(false);
    }
  }

  const sendPiCommand = async (command, label) => {
    if (command === 'reboot' && !confirm('⚠️ Pi wirklich neu starten?')) return;
    if (command === 'restart_service' && !confirm('Service wirklich neu starten?')) return;

    setCommandLoading(prev => ({ ...prev, [command]: true }));
    try {
      const res = await axios.post('/api/pi/command', { command });
      if (addToast) addToast('success', `${label}: Befehl gesendet`);
    } catch(err) {
      const msg = err.response?.data?.error || 'Fehler';
      if (addToast) addToast('error', `${label}: ${msg}`);
    } finally {
      setTimeout(() => {
        setCommandLoading(prev => ({ ...prev, [command]: false }));
      }, 2000);
    }
  }

  if (loading) return <div>Lade Einstellungen...</div>;

  const piButtons = [
    { command: 'git_pull', label: 'Git Pull', icon: <GitBranch size={16}/>, color: '#58a6ff', bg: 'rgba(88,166,255,0.15)', border: 'rgba(88,166,255,0.3)' },
    { command: 'restart_service', label: 'Service Restart', icon: <RotateCcw size={16}/>, color: '#d2a8ff', bg: 'rgba(210,168,255,0.15)', border: 'rgba(210,168,255,0.3)' },
    { command: 'wipe_buffer', label: 'Buffer Wipe', icon: <Eraser size={16}/>, color: '#f0883e', bg: 'rgba(240,136,62,0.15)', border: 'rgba(240,136,62,0.3)' },
    { command: 'reboot', label: 'Pi Reboot', icon: <Power size={16}/>, color: '#ff7b72', bg: 'rgba(255,123,114,0.15)', border: 'rgba(255,123,114,0.3)' },
  ];

  return (
    <div className="glass-card" style={{maxWidth: 800}}>
      <h3 style={{marginBottom: 24, display: 'flex', alignItems: 'center', gap: 8}}>
        <Settings size={22} color="#c9d1d9"/> Systemkonfiguration
      </h3>

      {/* === Remote Pi Management === */}
      <div className="glass-panel" style={{padding: 20, marginBottom: 24}}>
        <h4 style={{marginBottom: 16, color: '#3fb950', display: 'flex', alignItems: 'center', gap: 8}}>
          <Power size={18}/> Remote Pi Management
        </h4>
        <p style={{color: '#8b949e', fontSize: '0.85rem', marginBottom: 16}}>
          Befehle werden über MQTT an den Pi Zero gesendet. Rückmeldungen erscheinen als Benachrichtigungen.
        </p>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10}}>
          {piButtons.map(btn => (
            <button
              key={btn.command}
              onClick={() => sendPiCommand(btn.command, btn.label)}
              disabled={commandLoading[btn.command]}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                padding: '12px 16px',
                background: btn.bg,
                border: `1px solid ${btn.border}`,
                borderRadius: 10,
                color: btn.color,
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: commandLoading[btn.command] ? 'wait' : 'pointer',
                transition: 'all 0.2s ease',
                opacity: commandLoading[btn.command] ? 0.6 : 1,
                fontFamily: 'var(--font-family)',
              }}
              onMouseEnter={e => { if (!commandLoading[btn.command]) { e.target.style.transform = 'translateY(-2px)'; e.target.style.boxShadow = `0 4px 16px ${btn.bg}`; }}}
              onMouseLeave={e => { e.target.style.transform = 'translateY(0)'; e.target.style.boxShadow = 'none'; }}
            >
              {commandLoading[btn.command] ? <Loader2 size={16} className="spinner"/> : btn.icon}
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSave} className="flex-column gap-4">
        
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:24}}>
          <div className="glass-panel" style={{padding: 20}}>
            <h4 style={{marginBottom: 16, color:'#58a6ff'}}>Heatmap Einstellungen</h4>
            
            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">Heatmap Radius:</label>
              <input 
                type="number" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="heatmap_radius" 
                value={config.heatmap_radius || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">Heatmap Blur:</label>
              <input 
                type="number" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="heatmap_blur" 
                value={config.heatmap_blur || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-between" style={{background: 'rgba(255,255,255,0.05)', padding: 12, borderRadius: 8}}>
              <label className="text-muted mb-0">PNG Bilder generieren:</label>
              <input 
                type="checkbox" 
                name="heatmap_generate_png" 
                checked={config.heatmap_generate_png === 'on'} 
                onChange={handleChange} 
              />
            </div>
          </div>

          <div className="glass-panel" style={{padding: 20}}>
            <h4 style={{marginBottom: 16, color:'#2ea043'}}>Karten & Aufnahme</h4>
            
            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">Start Zoom (Karte):</label>
              <input 
                type="number" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="geo_zoom_start" 
                value={config.geo_zoom_start || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">GPS Speicherintervall (Sek.):</label>
              <input 
                type="number" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="rec_storage_interval" 
                value={config.rec_storage_interval || ''} 
                onChange={handleChange} 
              />
            </div>

             <div className="flex-between" style={{background: 'rgba(218,54,51,0.1)', padding: 12, borderRadius: 8, border: '1px solid rgba(218,54,51,0.2)'}}>
              <label className="text-danger mb-0">Test Mode (Mock Data):</label>
              <input 
                type="checkbox" 
                name="rec_test_mode" 
                checked={config.rec_test_mode === 'on'} 
                onChange={handleChange} 
              />
            </div>
          </div>
        </div>

        {/* --- GPS FILTERUNG & MODUL --- */}
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:24}}>
          <div className="glass-panel" style={{padding: 20}}>
            <h4 style={{marginBottom: 16, color:'#d2a8ff'}}>GPS Filterung (Post-Processing)</h4>
            
            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">Moving Average Window:</label>
              <input 
                type="number" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="moving_average_window" 
                value={config.moving_average_window || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">Kalman Measurement Noise:</label>
              <input 
                type="number" step="0.1" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="kalman_measurement_noise" 
                value={config.kalman_measurement_noise || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">Kalman Process Noise:</label>
              <input 
                type="number" step="0.01" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="kalman_process_noise" 
                value={config.kalman_process_noise || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">HDOP Schwellenwert:</label>
              <input 
                type="number" step="0.1" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="hdop_threshold" 
                value={config.hdop_threshold || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">Max Geschwindigkeit (m/s):</label>
              <input 
                type="number" step="0.1" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="max_speed_mps" 
                value={config.max_speed_mps || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-between" style={{background: 'rgba(255,255,255,0.05)', padding: 12, borderRadius: 8, marginBottom: 16}}>
              <label className="text-muted mb-0">Outlier Detection aktivieren:</label>
              <input 
                type="checkbox" 
                name="outlier_detection" 
                checked={config.outlier_detection === 'on'} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-between" style={{background: 'rgba(88,166,255,0.1)', padding: 12, borderRadius: 8, border: '1px solid rgba(88,166,255,0.2)'}}>
              <label className="text-muted mb-0" style={{color: '#58a6ff'}}>Dead Reckoning (IMU):</label>
              <input 
                type="checkbox" 
                name="dead_reckoning" 
                checked={config.dead_reckoning === 'on'} 
                onChange={handleChange} 
              />
            </div>
          </div>

          <div className="glass-panel" style={{padding: 20}}>
            <h4 style={{marginBottom: 16, color:'#f0883e'}}>Hardware & System</h4>
            
            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">GPS GNSS Modus (NEO-7M):</label>
              <select 
                className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)', background: 'rgba(13,17,23,0.8)'}} 
                name="gnss_mode" 
                value={config.gnss_mode || 'sbas'} 
                onChange={handleChange}
              >
                <option value="sbas">GPS + SBAS (EGNOS)</option>
                <option value="glonass">GPS + GLONASS (Mehr Satelliten)</option>
              </select>
              <small className="text-muted" style={{fontSize: '0.75rem', marginTop: 4}}>
                Hinweis: NEO-7M kann nicht beides gleichzeitig. Wird beim Speichern an den Pi übertragen.
              </small>
            </div>

            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">GPS Serial Port:</label>
              <input 
                type="text" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="gps_serial_port" 
                value={config.gps_serial_port || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-column mb-3" style={{gap:8, marginBottom: 16}}>
              <label className="text-muted">GPS Baudrate:</label>
              <input 
                type="number" className="glass-panel" 
                style={{padding: '8px 12px', color:'#fff', border:'1px solid rgba(255,255,255,0.1)'}} 
                name="gps_baudrate" 
                value={config.gps_baudrate || ''} 
                onChange={handleChange} 
              />
            </div>

            <div className="flex-between" style={{background: 'rgba(255,255,255,0.05)', padding: 12, borderRadius: 8}}>
              <label className="text-muted mb-0">Debug Logging:</label>
              <input 
                type="checkbox" 
                name="debug_logging" 
                checked={config.debug_logging === 'on'} 
                onChange={handleChange} 
              />
            </div>
          </div>
        </div>

        <div style={{marginTop: 32, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <button 
            type="button" 
            className="btn btn-danger" 
            onClick={handleDatabaseReset}
            disabled={resetting}
            style={{background: 'rgba(218,54,51,0.2)', border: '1px solid rgba(218,54,51,0.5)', color: '#ff7b72'}}
          >
            <Trash2 size={18}/> {resetting ? 'Lösche...' : 'Datenbank zurücksetzen'}
          </button>
          
          <button type="submit" className="btn btn-primary" disabled={saving}>
             <Save size={18}/> {saving ? 'Speichert...' : 'Einstellungen speichern'}
          </button>
        </div>

        <div style={{marginTop: 16, padding: 12, background: 'rgba(255,187,51,0.1)', border: '1px solid rgba(255,187,51,0.3)', borderRadius: 8}}>
          <div style={{display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8}}>
            <AlertTriangle size={16} color="#ffb347"/>
            <small style={{color: '#ffb347', fontWeight: 'bold'}}>
              Datenbank zurücksetzen:
            </small>
          </div>
          
          <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8}}>
            <input 
              type="checkbox" 
              id="includeGeofences"
              checked={includeGeofences}
              onChange={(e) => setIncludeGeofences(e.target.checked)}
              style={{margin: 0}}
            />
            <label htmlFor="includeGeofences" style={{color: '#ffb347', margin: 0, cursor: 'pointer'}}>
              Auch Geofences löschen
            </label>
          </div>
          
          <small style={{color: '#ffb347', display: 'block'}}>
            {includeGeofences 
              ? 'Löscht alle Mähsessions, Geofences und Heatmaps. Nur Konfiguration bleibt erhalten.'
              : 'Löscht alle Mähsessions und Heatmaps. Geofences und Konfiguration bleiben erhalten.'
            }
          </small>
        </div>
      </form>
    </div>
  )
}
