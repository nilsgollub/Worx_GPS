import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Activity, Filter, RefreshCw, Trash2, AlertCircle, Info, AlertTriangle, CheckCircle } from 'lucide-react';

const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
const LEVEL_COLORS = {
  DEBUG: '#8b949e',
  INFO: '#58a6ff',
  WARNING: '#ffb347',
  ERROR: '#ff7b72'
};

const LEVEL_ICONS = {
  DEBUG: Info,
  INFO: CheckCircle,
  WARNING: AlertTriangle,
  ERROR: AlertCircle
};

export default function Logs() {
  const [logs, setLogs] = useState([]);
  const [sources, setSources] = useState([]);
  const [levelFilter, setLevelFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [limit, setLimit] = useState(100);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const logContainerRef = useRef(null);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (levelFilter) params.append('level', levelFilter);
      if (sourceFilter) params.append('source', sourceFilter);
      params.append('limit', limit);
      
      const res = await axios.get(`/api/logs?${params}`);
      setLogs(res.data.logs || []);
    } catch (err) {
      console.error('Fehler beim Laden der Logs:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchSources = async () => {
    try {
      const res = await axios.get('/api/logs/sources');
      setSources(res.data.sources || []);
    } catch (err) {
      console.error('Fehler beim Laden der Quellen:', err);
    }
  };

  const clearLogs = () => {
    setLogs([]);
  };

  const scrollToBottom = () => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    fetchLogs();
    fetchSources();
  }, [levelFilter, sourceFilter, limit]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchLogs();
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, levelFilter, sourceFilter, limit]);

  useEffect(() => {
    scrollToBottom();
  }, [logs]);

  const formatTimestamp = (timestamp) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('de-DE', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
      });
    } catch {
      return timestamp;
    }
  };

  const getLevelIcon = (level) => {
    const Icon = LEVEL_ICONS[level] || Info;
    return <Icon size={14} color={LEVEL_COLORS[level] || '#8b949e'} />;
  };

  return (
    <div className="glass-card" style={{maxWidth: 1200}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24}}>
        <Activity size={22} color="#c9d1d9"/>
        <h3 style={{margin: 0}}>System Logs</h3>
        <span style={{color: '#8b949e', fontSize: '0.9em'}}>
          ({logs.length} von {limit} Einträgen)
        </span>
      </div>

      {/* Filter Controls */}
      <div className="glass-panel" style={{padding: 16, marginBottom: 20}}>
        <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, alignItems: 'end'}}>
          <div>
            <label style={{display: 'block', marginBottom: 4, color: '#8b949e', fontSize: '0.9em'}}>
              Log Level
            </label>
            <select 
              value={levelFilter} 
              onChange={(e) => setLevelFilter(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                background: 'rgba(255,255,255,0.1)',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 6,
                color: '#fff'
              }}
            >
              <option value="">Alle Levels</option>
              {LOG_LEVELS.map(level => (
                <option key={level} value={level}>{level}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{display: 'block', marginBottom: 4, color: '#8b949e', fontSize: '0.9em'}}>
              Quelle
            </label>
            <select 
              value={sourceFilter} 
              onChange={(e) => setSourceFilter(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                background: 'rgba(255,255,255,0.1)',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 6,
                color: '#fff'
              }}
            >
              <option value="">Alle Quellen</option>
              {sources.map(source => (
                <option key={source} value={source}>{source}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{display: 'block', marginBottom: 4, color: '#8b949e', fontSize: '0.9em'}}>
              Limit
            </label>
            <select 
              value={limit} 
              onChange={(e) => setLimit(Number(e.target.value))}
              style={{
                width: '100%',
                padding: '8px 12px',
                background: 'rgba(255,255,255,0.1)',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 6,
                color: '#fff'
              }}
            >
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </select>
          </div>

          <div style={{display: 'flex', gap: 8}}>
            <button 
              onClick={fetchLogs}
              disabled={loading}
              className="btn btn-primary"
              style={{padding: '8px 16px'}}
            >
              <RefreshCw size={16} style={{marginRight: 4}}/>
              {loading ? 'Lädt...' : 'Aktualisieren'}
            </button>

            <button 
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`btn ${autoRefresh ? 'btn-success' : ''}`}
              style={{
                padding: '8px 16px',
                background: autoRefresh ? 'rgba(56,139,253,0.2)' : 'rgba(255,255,255,0.1)',
                border: autoRefresh ? '1px solid rgba(56,139,253,0.5)' : '1px solid rgba(255,255,255,0.2)'
              }}
            >
              Auto: {autoRefresh ? 'ON' : 'OFF'}
            </button>

            <button 
              onClick={clearLogs}
              className="btn"
              style={{
                padding: '8px 16px',
                background: 'rgba(218,54,51,0.2)',
                border: '1px solid rgba(218,54,51,0.5)',
                color: '#ff7b72'
              }}
            >
              <Trash2 size={16}/>
            </button>
          </div>
        </div>
      </div>

      {/* Log Container */}
      <div 
        ref={logContainerRef}
        className="glass-panel" 
        style={{ 
          padding: 16, 
          height: '600px', 
          overflowY: 'auto',
          fontFamily: 'Consolas, Monaco, monospace',
          fontSize: '0.85em',
          lineHeight: 1.4
        }}
      >
        {logs.length === 0 ? (
          <div style={{textAlign: 'center', color: '#8b949e', padding: 40}}>
            {loading ? 'Lade Logs...' : 'Keine Logs gefunden'}
          </div>
        ) : (
          <div style={{display: 'flex', flexDirection: 'column', gap: 4}}>
            {logs.map((log, index) => (
              <div 
                key={index}
                style={{
                  display: 'flex',
                  gap: 12,
                  padding: '6px 8px',
                  borderRadius: 4,
                  background: 'rgba(255,255,255,0.02)',
                  borderLeft: `3px solid ${LEVEL_COLORS[log.level] || '#8b949e'}`
                }}
              >
                <span style={{color: '#8b949e', minWidth: 80, fontSize: '0.9em'}}>
                  {formatTimestamp(log.timestamp)}
                </span>
                <span style={{color: LEVEL_COLORS[log.level], minWidth: 70, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 4}}>
                  {getLevelIcon(log.level)}
                  {log.level}
                </span>
                <span style={{color: '#58a6ff', minWidth: 100, fontSize: '0.9em'}}>
                  {log.source}
                </span>
                <span style={{color: '#c9d1d9', flex: 1, wordBreak: 'break-word'}}>
                  {log.message}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
