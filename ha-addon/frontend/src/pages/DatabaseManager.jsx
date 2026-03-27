import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Database, Download, Trash2, RefreshCw, FileJson, FileSpreadsheet, 
  HardDrive, ChevronDown, ChevronUp, Filter, Eye, BarChart3, TrendingUp
} from 'lucide-react';
import { API_URL } from '../App';

export default function DatabaseManager() {
  const [dbInfo, setDbInfo] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [qualityStats, setQualityStats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedSession, setExpandedSession] = useState(null);
  const [sessionDetail, setSessionDetail] = useState(null);
  const [showQuality, setShowQuality] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [infoRes, sessionsRes] = await Promise.all([
        axios.get('/api/database/info'),
        axios.get('/api/database/sessions')
      ]);
      setDbInfo(infoRes.data);
      setSessions(sessionsRes.data.sessions || []);
    } catch (e) {
      console.error('Error fetching database info', e);
    } finally {
      setLoading(false);
    }
  };

  const fetchQualityStats = async () => {
    try {
      const res = await axios.get('/api/database/sessions/quality');
      setQualityStats(res.data.stats || []);
      setShowQuality(true);
    } catch (e) {
      console.error('Error fetching quality stats', e);
    }
  };

  const fetchSessionDetail = async (sessionId) => {
    if (expandedSession === sessionId) {
      setExpandedSession(null);
      setSessionDetail(null);
      return;
    }
    try {
      const res = await axios.get(`/api/database/sessions/${sessionId}`);
      setSessionDetail(res.data);
      setExpandedSession(sessionId);
    } catch (e) {
      console.error('Error fetching session detail', e);
    }
  };

  const deleteSession = async (sessionId) => {
    if (!window.confirm(`Session #${sessionId} wirklich löschen?`)) return;
    try {
      await axios.delete(`/api/database/sessions/${sessionId}`);
      fetchData();
      if (expandedSession === sessionId) {
        setExpandedSession(null);
        setSessionDetail(null);
      }
    } catch (e) {
      alert('Fehler beim Löschen');
    }
  };

  useEffect(() => { fetchData(); }, []);

  const formatBytes = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '-';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return m > 0 ? `${m}m ${s}s` : `${s}s`;
  };

  if (loading) {
    return <div className="glass-panel" style={{padding: 40, textAlign: 'center'}}><RefreshCw className="spinner" /> Lade Datenbank...</div>;
  }

  return (
    <div className="flex-column gap-4">
      
      {/* DB Info Cards */}
      <div className="dashboard-grid" style={{gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))'}}>
        <div className="glass-card flex-column" style={{gap: 8, alignItems: 'center', padding: 20}}>
          <HardDrive size={28} color="#58a6ff" />
          <h2 style={{margin: 0, fontSize: 28}}>{dbInfo?.db_size_mb || 0} MB</h2>
          <span className="text-muted text-small">Datenbankgröße</span>
        </div>
        <div className="glass-card flex-column" style={{gap: 8, alignItems: 'center', padding: 20}}>
          <Database size={28} color="#3fb950" />
          <h2 style={{margin: 0, fontSize: 28}}>{dbInfo?.session_count || 0}</h2>
          <span className="text-muted text-small">Sessions</span>
        </div>
        <div className="glass-card flex-column" style={{gap: 8, alignItems: 'center', padding: 20}}>
          <BarChart3 size={28} color="#d29922" />
          <h2 style={{margin: 0, fontSize: 28}}>{(dbInfo?.point_count || 0).toLocaleString()}</h2>
          <span className="text-muted text-small">GPS-Punkte</span>
        </div>
        <div className="glass-card flex-column" style={{gap: 8, alignItems: 'center', padding: 20}}>
          <Filter size={28} color="#f0883e" />
          <h2 style={{margin: 0, fontSize: 28}}>{dbInfo?.geofence_count || 0}</h2>
          <span className="text-muted text-small">Geofences</span>
        </div>
      </div>

      {/* Actions Bar */}
      <div className="glass-panel" style={{padding: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center'}}>
        <button className="btn btn-primary" onClick={fetchData} style={{padding: '8px 16px'}}>
          <RefreshCw size={16} /> Aktualisieren
        </button>
        <a href={`${API_URL}/api/database/export/all`} className="btn" style={{padding: '8px 16px', background: 'rgba(63,185,80,0.2)', border: '1px solid rgba(63,185,80,0.4)', color: '#3fb950', textDecoration: 'none'}}>
          <Download size={16} /> Alles exportieren (JSON)
        </a>
        <button className="btn" onClick={fetchQualityStats} style={{padding: '8px 16px', background: 'rgba(210,169,34,0.2)', border: '1px solid rgba(210,169,34,0.4)', color: '#d2a922'}}>
          <TrendingUp size={16} /> Qualitäts-Analyse
        </button>
        <span className="text-muted text-small" style={{marginLeft: 'auto'}}>
          Pfad: {dbInfo?.db_path || '-'}
        </span>
      </div>

      {/* Quality Stats Panel */}
      {showQuality && qualityStats.length > 0 && (
        <div className="glass-card">
          <div className="flex-between mb-4">
            <h3 style={{margin: 0}}><TrendingUp size={20} className="mr-2" /> Empfangsqualität über Zeit</h3>
            <button className="btn" style={{padding: '4px 8px'}} onClick={() => setShowQuality(false)}>Schließen</button>
          </div>
          <div style={{overflowX: 'auto'}}>
            <table style={{width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85em'}}>
              <thead>
                <tr style={{borderBottom: '1px solid rgba(255,255,255,0.1)'}}>
                  <th style={{padding: '8px 12px', color: '#888'}}>Datum</th>
                  <th style={{padding: '8px 12px', color: '#888'}}>Punkte</th>
                  <th style={{padding: '8px 12px', color: '#888'}}>Dauer</th>
                  <th style={{padding: '8px 12px', color: '#888'}}>Distanz</th>
                  <th style={{padding: '8px 12px', color: '#888'}}>Ø Sats</th>
                  <th style={{padding: '8px 12px', color: '#888'}}>Ø HDOP</th>
                  <th style={{padding: '8px 12px', color: '#888'}}>Min HDOP</th>
                  <th style={{padding: '8px 12px', color: '#888'}}>Max HDOP</th>
                  <th style={{padding: '8px 12px', color: '#888'}}>Coverage</th>
                  <th style={{padding: '8px 12px', color: '#888'}}>Dead Reck.</th>
                </tr>
              </thead>
              <tbody>
                {qualityStats.map((stat, i) => (
                  <tr key={stat.id} style={{borderBottom: '1px solid rgba(255,255,255,0.05)'}}>
                    <td style={{padding: '8px 12px'}}>{stat.start_time || '-'}</td>
                    <td style={{padding: '8px 12px'}}>{stat.point_count || 0}</td>
                    <td style={{padding: '8px 12px'}}>{formatDuration(stat.duration_seconds)}</td>
                    <td style={{padding: '8px 12px', fontFamily: 'monospace'}}>{stat.distance_meters ? `${(stat.distance_meters/1000).toFixed(2)} km` : '-'}</td>
                    <td style={{padding: '8px 12px', fontFamily: 'monospace', color: stat.avg_satellites >= 8 ? '#3fb950' : stat.avg_satellites >= 5 ? '#d29922' : '#ff7b72'}}>
                      {stat.avg_satellites?.toFixed(1) || '-'}
                    </td>
                    <td style={{padding: '8px 12px', fontFamily: 'monospace', color: stat.avg_hdop <= 1.5 ? '#3fb950' : stat.avg_hdop <= 3 ? '#d29922' : '#ff7b72'}}>
                      {stat.avg_hdop?.toFixed(2) || '-'}
                    </td>
                    <td style={{padding: '8px 12px', fontFamily: 'monospace'}}>{stat.min_hdop?.toFixed(2) || '-'}</td>
                    <td style={{padding: '8px 12px', fontFamily: 'monospace'}}>{stat.max_hdop?.toFixed(2) || '-'}</td>
                    <td style={{padding: '8px 12px', color: '#a6d96a'}}>{stat.coverage ? `${stat.coverage}%` : '-'}</td>
                    <td style={{padding: '8px 12px'}}>
                      {stat.filter_config ? (
                        <span className={`badge ${stat.filter_config.dead_reckoning_enabled ? 'success' : 'secondary'}`} style={{fontSize: '0.75em'}}>
                          {stat.filter_config.dead_reckoning_enabled ? 'AN' : 'AUS'}
                        </span>
                      ) : <span className="text-muted">-</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sessions Table */}
      <div className="glass-card">
        <h3 className="mb-4" style={{display: 'flex', alignItems: 'center', gap: 8}}>
          <Database size={20} /> Sessions ({sessions.length})
        </h3>
        <div style={{overflowX: 'auto'}}>
          <table style={{width: '100%', borderCollapse: 'collapse', textAlign: 'left'}}>
            <thead>
              <tr style={{borderBottom: '1px solid rgba(255,255,255,0.1)'}}>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500}}>ID</th>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500}}>Datum</th>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500}}>Dauer</th>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500}}>Punkte</th>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500}}>Distanz</th>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500}}>Coverage</th>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500}}>Ø Sats</th>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500}}>Ø HDOP</th>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500}}>Filter</th>
                <th style={{padding: '12px 16px', color: '#888', fontWeight: 500, textAlign: 'right'}}>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <React.Fragment key={session.id}>
                  <tr style={{borderBottom: '1px solid rgba(255,255,255,0.05)', cursor: 'pointer'}} onClick={() => fetchSessionDetail(session.id)}>
                    <td style={{padding: '12px 16px', fontFamily: 'monospace', color: '#58a6ff'}}>#{session.id}</td>
                    <td style={{padding: '12px 16px'}}>{session.start_time || '-'}</td>
                    <td style={{padding: '12px 16px'}}>{formatDuration(session.duration_seconds)}</td>
                    <td style={{padding: '12px 16px'}}>{session.actual_point_count || session.point_count || 0}</td>
                    <td style={{padding: '12px 16px', fontFamily: 'monospace'}}>{session.distance_meters ? `${(session.distance_meters/1000).toFixed(2)} km` : '-'}</td>
                    <td style={{padding: '12px 16px', color: '#a6d96a'}}>{session.coverage ? `${session.coverage}%` : '-'}</td>
                    <td style={{padding: '12px 16px', fontFamily: 'monospace'}}>
                      {session.avg_satellites?.toFixed(1) || '-'}
                    </td>
                    <td style={{padding: '12px 16px', fontFamily: 'monospace'}}>
                      {session.avg_hdop?.toFixed(2) || '-'}
                    </td>
                    <td style={{padding: '12px 16px'}}>
                      {session.filter_config ? (
                        <span className="badge info" style={{fontSize: '0.7em'}}>
                          {session.filter_config.dead_reckoning_enabled ? 'DR' : ''} 
                          {session.filter_config.method || ''}
                        </span>
                      ) : <span className="text-muted">-</span>}
                    </td>
                    <td style={{padding: '12px 16px', textAlign: 'right'}} onClick={e => e.stopPropagation()}>
                      <div style={{display: 'flex', gap: 4, justifyContent: 'flex-end'}}>
                        <a href={`${API_URL}/api/database/sessions/${session.id}/export/csv`} className="btn" style={{padding: '4px 8px', background: 'rgba(255,255,255,0.05)'}} title="CSV Export">
                          <FileSpreadsheet size={14} />
                        </a>
                        <a href={`${API_URL}/api/database/sessions/${session.id}/export/json`} className="btn" style={{padding: '4px 8px', background: 'rgba(255,255,255,0.05)'}} title="JSON Export">
                          <FileJson size={14} />
                        </a>
                        <button className="btn btn-danger" style={{padding: '4px 8px'}} onClick={() => deleteSession(session.id)} title="Löschen">
                          <Trash2 size={14} />
                        </button>
                        <button className="btn" style={{padding: '4px 8px', background: 'rgba(255,255,255,0.05)'}} title="Details">
                          {expandedSession === session.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                      </div>
                    </td>
                  </tr>
                  
                  {/* Expanded Detail Row */}
                  {expandedSession === session.id && sessionDetail && (
                    <tr>
                      <td colSpan={10} style={{padding: 0}}>
                        <div style={{padding: 20, background: 'rgba(0,0,0,0.2)', borderBottom: '2px solid rgba(88,166,255,0.3)'}}>
                          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16}}>
                            
                            {/* Session Metadata */}
                            <div className="glass-panel" style={{padding: 16}}>
                              <h4 style={{marginBottom: 12, color: '#58a6ff'}}>Session Metadaten</h4>
                              <div style={{display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.85em'}}>
                                <div className="flex-between"><span className="text-muted">Filename:</span><span style={{fontFamily: 'monospace'}}>{sessionDetail.filename}</span></div>
                                <div className="flex-between"><span className="text-muted">Start:</span><span>{sessionDetail.start_time}</span></div>
                                <div className="flex-between"><span className="text-muted">Ende:</span><span>{sessionDetail.end_time || '-'}</span></div>
                                <div className="flex-between"><span className="text-muted">Dauer:</span><span>{formatDuration(sessionDetail.duration_seconds)}</span></div>
                                <div className="flex-between"><span className="text-muted">Distanz:</span><span>{sessionDetail.distance_meters ? `${(sessionDetail.distance_meters/1000).toFixed(3)} km` : '-'}</span></div>
                                <div className="flex-between"><span className="text-muted">Punkte:</span><span>{sessionDetail.point_count}</span></div>
                                <div className="flex-between"><span className="text-muted">Coverage:</span><span style={{color: '#a6d96a'}}>{sessionDetail.coverage}%</span></div>
                                <div className="flex-between"><span className="text-muted">Ø Satelliten:</span><span>{sessionDetail.avg_satellites?.toFixed(1) || '-'}</span></div>
                                <div className="flex-between"><span className="text-muted">Ø HDOP:</span><span>{sessionDetail.avg_hdop?.toFixed(2) || '-'}</span></div>
                              </div>
                            </div>

                            {/* Filter Config */}
                            <div className="glass-panel" style={{padding: 16}}>
                              <h4 style={{marginBottom: 12, color: '#d2a8ff'}}>Filter-Konfiguration (Aufnahme-DNA)</h4>
                              {sessionDetail.filter_config ? (
                                <div style={{display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.85em'}}>
                                  <div className="flex-between"><span className="text-muted">Methode:</span><span>{sessionDetail.filter_config.method || '-'}</span></div>
                                  <div className="flex-between"><span className="text-muted">Kalman Mess-Rauschen:</span><span style={{fontFamily:'monospace'}}>{sessionDetail.filter_config.kalman_measurement_noise ?? '-'}</span></div>
                                  <div className="flex-between"><span className="text-muted">Kalman Proz-Rauschen:</span><span style={{fontFamily:'monospace'}}>{sessionDetail.filter_config.kalman_process_noise ?? '-'}</span></div>
                                  <div className="flex-between"><span className="text-muted">HDOP Schwelle:</span><span style={{fontFamily:'monospace'}}>{sessionDetail.filter_config.hdop_threshold ?? '-'}</span></div>
                                  <div className="flex-between"><span className="text-muted">Max Speed:</span><span style={{fontFamily:'monospace'}}>{sessionDetail.filter_config.max_speed_mps ?? '-'} m/s</span></div>
                                  <div className="flex-between"><span className="text-muted">Dead Reckoning:</span>
                                    <span className={`badge ${sessionDetail.filter_config.dead_reckoning_enabled ? 'success' : 'danger'}`} style={{fontSize: '0.8em'}}>
                                      {sessionDetail.filter_config.dead_reckoning_enabled ? 'Aktiv' : 'Aus'}
                                    </span>
                                  </div>
                                  <div className="flex-between"><span className="text-muted">Outlier Detection:</span>
                                    <span className={`badge ${sessionDetail.filter_config.outlier_detection_enable ? 'success' : 'danger'}`} style={{fontSize: '0.8em'}}>
                                      {sessionDetail.filter_config.outlier_detection_enable ? 'Aktiv' : 'Aus'}
                                    </span>
                                  </div>
                                  <div className="flex-between"><span className="text-muted">Moving Avg Window:</span><span style={{fontFamily:'monospace'}}>{sessionDetail.filter_config.moving_average_window ?? '-'}</span></div>
                                </div>
                              ) : (
                                <p className="text-muted" style={{fontSize: '0.85em'}}>Keine Filter-Daten gespeichert (ältere Session).</p>
                              )}
                            </div>

                            {/* GPS Points Preview */}
                            <div className="glass-panel" style={{padding: 16}}>
                              <h4 style={{marginBottom: 12, color: '#f0883e'}}>GPS-Punkte Vorschau (erste 10)</h4>
                              <div style={{maxHeight: 250, overflowY: 'auto', fontSize: '0.75em', fontFamily: 'monospace'}}>
                                {sessionDetail.points?.slice(0, 10).map((p, i) => (
                                  <div key={i} style={{padding: '4px 0', borderBottom: '1px solid rgba(255,255,255,0.05)'}}>
                                    <span style={{color: '#58a6ff'}}>#{i+1}</span>{' '}
                                    <span>{p.lat?.toFixed(6)}, {p.lon?.toFixed(6)}</span>{' '}
                                    <span className="text-muted">Sats:{p.satellites} HDOP:{p.hdop?.toFixed(1) || '-'}</span>
                                  </div>
                                ))}
                                {(sessionDetail.points?.length || 0) > 10 && (
                                  <div className="text-muted" style={{padding: '8px 0'}}>... und {sessionDetail.points.length - 10} weitere Punkte</div>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {sessions.length === 0 && (
                <tr>
                  <td colSpan={10} style={{padding: 24, textAlign: 'center', color: '#888'}}>
                    Keine Sessions in der Datenbank.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
