import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Settings, Save } from 'lucide-react';

export default function Config() {
  const [config, setConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    axios.get('/api/config').then(res => {
      setConfig(res.data.config || {});
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

  if (loading) return <div>Lade Einstellungen...</div>;

  return (
    <div className="glass-card" style={{maxWidth: 800}}>
      <h3 style={{marginBottom: 24, display: 'flex', alignItems: 'center', gap: 8}}>
        <Settings size={22} color="#c9d1d9"/> Systemkonfiguration
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

        <div style={{marginTop: 24, textAlign: 'right'}}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
             <Save size={18}/> {saving ? 'Speichert...' : 'Einstellungen speichern'}
          </button>
        </div>
      </form>
    </div>
  )
}
