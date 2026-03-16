import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Calendar, AlertTriangle, PlayCircle, Clock, Trash2, ShieldAlert } from 'lucide-react';

export default function Stats() {
  const [data, setData] = useState({
    stats: {},
    problem_zones: [],
    mow_sessions: []
  });

  const fetchData = async () => {
    try {
      const res = await axios.get('/api/stats');
      setData({
        stats: res.data.stats || {},
        problem_zones: res.data.problem_zones || [],
        mow_sessions: res.data.mow_sessions || []
      });
    } catch(err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleDeleteSession = async (filename) => {
    if(window.confirm(`Session ${filename} wirklich löschen?`)) {
      try {
        await axios.post(`/mow_session/delete/${filename}`);
        fetchData();
      } catch(e) {
        alert('Fehler beim Löschen');
      }
    }
  }

  const { stats, problem_zones, mow_sessions } = data;

  return (
    <div className="flex-column gap-4">
      {/* Top Cards */}
      <div className="dashboard-grid" style={{gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))'}}>
        <div className="glass-card flex-column" style={{gap:16, alignItems:'center', justifyContent:'center', padding:30}}>
          <Calendar size={36} color="#d29922" />
          <h2 style={{margin:0, fontSize:36}}>{stats.total_recordings || 0}</h2>
          <span className="text-muted">Aufgezeichnete Mähvorgänge</span>
        </div>

        <div className="glass-card flex-column" style={{gap:16, alignItems:'center', justifyContent:'center', padding:30}}>
          <AlertTriangle size={36} color="#ff7b72" />
          <h2 style={{margin:0, fontSize:36}}>{stats.problem_zones_count || 0}</h2>
          <span className="text-muted">Erkannte Problemzonen</span>
        </div>

        <div className="glass-card flex-column" style={{gap:16, alignItems:'center', justifyContent:'center', padding:30}}>
          <Clock size={36} color="#2ea043" />
          <h2 style={{margin:0, fontSize:36}}>{stats.last_coverage || 0}%</h2>
          <span className="text-muted">Coverage (Letzter Lauf)</span>
        </div>
        
        <div className="glass-card flex-column" style={{gap:16, alignItems:'center', justifyContent:'center', padding:30}}>
          <Clock size={36} color="#2e70ff" />
          <h2 style={{margin:0, fontSize:36}}>{stats.total_coverage || 0}%</h2>
          <span className="text-muted">Coverage (Gesamt)</span>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="glass-card flex-column" style={{gridColumn: '1 / span 2'}}>
          <h3 className="mb-4" style={{marginBottom: 20}}>
            <PlayCircle size={20} style={{marginRight:8}}/> 
            Mähvorgänge
          </h3>
          <div style={{overflowX: 'auto'}}>
            <table style={{width: '100%', borderCollapse: 'collapse', textAlign: 'left'}}>
              <thead>
                <tr style={{borderBottom: '1px solid rgba(255,255,255,0.1)'}}>
                  <th style={{padding: '12px 16px', color:'#888', fontWeight:500}}>Datum</th>
                  <th style={{padding: '12px 16px', color:'#888', fontWeight:500}}>Dauer</th>
                  <th style={{padding: '12px 16px', color:'#888', fontWeight:500}}>Distanz</th>
                  <th style={{padding: '12px 16px', color:'#888', fontWeight:500}}>Abdeckung</th>
                  <th style={{padding: '12px 16px', color:'#888', fontWeight:500, textAlign:'right'}}>Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {mow_sessions.map((session, i) => (
                  <tr key={session.filename} style={{borderBottom: '1px solid rgba(255,255,255,0.05)'}}>
                    <td style={{padding: '12px 16px'}}>{session.start_time_str || 'N/A'}</td>
                    <td style={{padding: '12px 16px'}}>{session.duration_str || '-'}</td>
                    <td style={{padding: '12px 16px', fontFamily:'monospace'}}>{session.distance_km_str || '-'}</td>
                    <td style={{padding: '12px 16px', fontFamily:'monospace', color: '#a6d96a'}}>{session.coverage_str || '-'}</td>
                    <td style={{padding: '12px 16px', textAlign:'right'}}>
                      <button 
                        className="btn btn-danger" 
                        style={{padding:'6px 10px'}}
                        onClick={() => handleDeleteSession(session.filename)}
                      >
                        <Trash2 size={16}/>
                      </button>
                    </td>
                  </tr>
                ))}
                {mow_sessions.length === 0 && (
                  <tr>
                    <td colSpan={4} style={{padding: 24, textAlign: 'center', color: '#888'}}>
                      Keine Aufzeichnungen vorhanden.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="glass-card flex-column">
           <h3 className="mb-4" style={{marginBottom: 20}}>
            <ShieldAlert size={20} style={{marginRight:8}}/> 
            Letzte Problemzonen
          </h3>
          <div className="flex-column" style={{gap:12}}>
            {problem_zones.slice(0, 10).map((zone, i) => (
              <div key={i} className="glass-panel" style={{padding: '12px', background: 'rgba(255,255,255,0.02)'}}>
                <div className="flex-between">
                  <strong>{zone.zeitpunkt || "Unbekannt"}</strong>
                  <span className="badge warning">Problem</span>
                </div>
                <div className="text-small text-muted mt-2" style={{fontFamily: 'monospace'}}>
                  {zone.position}
                </div>
              </div>
            ))}
            {problem_zones.length === 0 && <span className="text-muted">Keine Probleme erkannt.</span>}
          </div>
        </div>
      </div>
    </div>
  )
}
