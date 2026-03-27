import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, Save, Trash2, AlertTriangle } from 'lucide-react';

export default function Config() {
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [includeGeofences, setIncludeGeofences] = useState(false);

  useEffect(() => {
    axios.get('/api/config').then(res => {
      const cfg = res.data.config || {};
      // Convert booleans to 'on'/'off' for React checkbox state consistency
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
      alert(res.data.message);
    } catch(err) {
      alert('Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const handleDatabaseReset = async () => {
    const geofenceText = includeGeofences ? ' und alle Geofences' : '';
    const warningText = `⚠️ Wirklich alle Mähsessions${geofenceText} löschen?\n\nDiese Aktion kann nicht rückgängig gemacht werden. Alle Heatmaps werden ebenfalls gelöscht.`;
    
    if (!confirm(warningText)) {
      return;
    }

    setResetting(true);
    try {
      const res = await axios.post('/api/database/reset', { include_geofences: includeGeofences });
      alert(res.data.message);
      // Seite neu laden um Statistiken zu aktualisieren
      window.location.reload();
    } catch(err) {
      const message = err.response?.data?.message || 'Fehler beim Zurücksetzen der Datenbank';
      alert(message);
    } finally {
      setResetting(false);
    }
  }

  if (loading) return <div>Lade Einstellungen...</div>;

  return (
    <div className="glass-card" style={{maxWidth: 800}}>
      <h3 style={{marginBottom: 24, display: 'flex', alignItems: 'center', gap: 8}}>
        <Settings size={22} color="#c9d1d9"/> Systemkonfiguration (v2.3.0)
      </h3>

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

        {/* --- NEUE ZEILE FÜR GPS FILTERUNG & MODUL --- */}
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
                Hinweis: NEO-7M kann nicht beides gleichzeitig.
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
