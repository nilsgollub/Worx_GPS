import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { ExternalLink } from 'lucide-react';
import { API_URL } from '../App';

export default function Maps() {
  const [maps, setMaps] = useState([]);
  const [selectedMap, setSelectedMap] = useState(null);

  useEffect(() => {
    axios.get('/api/heatmaps').then(res => {
      setMaps(res.data.heatmaps || []);
      if (res.data.heatmaps && res.data.heatmaps.length > 0) {
        setSelectedMap(res.data.heatmaps[0]);
      }
    });
  }, []);

  return (
    <div style={{display: 'flex', gap: 24, height: 'calc(100vh - 120px)'}}>
      <div className="glass-panel" style={{width: 300, padding: 16, display: 'flex', flexDirection: 'column'}}>
        <h3 style={{marginBottom: 16}}>Verfügbare Karten</h3>
        <div style={{display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto'}}>
          {maps.map(m => (
            <button
              key={m.id}
              className={`btn ${selectedMap?.id === m.id ? 'btn-primary' : ''}`}
              style={{
                justifyContent: 'flex-start',
                background: selectedMap?.id === m.id ? '' : 'rgba(255,255,255,0.05)',
                color: selectedMap?.id === m.id ? '#fff' : '#c9d1d9'
              }}
              onClick={() => setSelectedMap(m)}
            >
              {m.name}
              {m.png_path && <span className="badge secondary ml-auto" style={{marginLeft:'auto'}}>PNG</span>}
            </button>
          ))}
          {maps.length === 0 && <span className="text-muted">Keine Karten vorhanden</span>}
        </div>
      </div>

      <div className="glass-card" style={{flex: 1, padding: 0, overflow: 'hidden', display:'flex', flexDirection:'column'}}>
        <div className="flex-between" style={{padding: '16px 24px', borderBottom: '1px solid rgba(255,255,255,0.05)'}}>
          <h3 style={{margin: 0}}>{selectedMap ? selectedMap.name : 'Keine Karte gewählt'}</h3>
          {selectedMap && (
            <a 
              href={`${API_URL}/heatmaps/${selectedMap.id}.html`} 
              target="_blank" 
              className="btn btn-primary" 
              style={{padding: '6px 12px'}}
            >
              Im Tab öffnen <ExternalLink size={14} />
            </a>
          )}
        </div>
        <div style={{flex: 1, background: '#111'}}>
          {selectedMap ? (
            <iframe 
               src={`${API_URL}/heatmaps/${selectedMap.id}.html`} 
               style={{width: '100%', height:'100%', border: 'none'}} 
            />
          ) : (
            <div style={{display: 'flex', alignItems: 'center', justifyContent:'center', height:'100%', color:'#888'}}>
              Vorschau nicht verfügbar.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
