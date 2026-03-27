import React, { useState, useEffect } from 'react';

import { HashRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';

import { RadioTower, Map, Activity, Settings, Server, Menu, X, Power, PowerOff, Shield, Navigation, FileText, Database } from 'lucide-react';

import Dashboard from './pages/Dashboard';
import Maps from './pages/Maps';
import Geofence from './pages/Geofence';
import Live from './pages/Live';
import Config from './pages/Config';
import Stats from './pages/Stats';
import Logs from './pages/Logs';
import MowerControl from './pages/MowerControl';
import DatabaseManager from './pages/DatabaseManager';
import { io } from 'socket.io-client';
import axios from 'axios';

const isDev = import.meta.env.DEV;
const basePath = window.location.pathname.replace(/\/$/, '');
export const API_URL = isDev ? 'http://localhost:5001' : basePath;
export const socket = io(isDev ? 'http://localhost:5001' : undefined, {
    path: isDev ? '/socket.io' : `${basePath}/socket.io`
});

axios.defaults.baseURL = API_URL;

function Sidebar() {
  const location = useLocation();

  const links = [
    { to: '/', icon: <Activity size={20} />, label: 'Dashboard' },
    { to: '/control', icon: <Server size={20} />, label: 'Mäher-Steuerung' },
    { to: '/live', icon: <Navigation size={20} />, label: 'Live-Radar' },
    { to: '/geofence', icon: <Shield size={20} />, label: 'Zonen-Editor' },
    { to: '/maps', icon: <Map size={20} />, label: 'Historie' },
    { to: '/stats', icon: <RadioTower size={20} />, label: 'Statistiken' },
    { to: '/database', icon: <Database size={20} />, label: 'Datenbank' },
    { to: '/logs', icon: <FileText size={20} />, label: 'Logs' },
    { to: '/config', icon: <Settings size={20} />, label: 'Einstellungen' },
  ];

  return (
    <div className="sidebar">
      <div className="flex-between" style={{ alignItems: 'center' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Server color="#2f81f7" /> Worx GPS
        </h2>
      </div>

      <nav className="nav-menu">
        {links.map((link) => (
          <Link
            key={link.to}
            to={link.to}
            className={`nav-item ${location.pathname === link.to ? 'active' : ''}`}
          >
            {link.icon}
            {link.label}
          </Link>
        ))}
      </nav>

      <div style={{ marginTop: 'auto' }}>
        <button className="btn btn-danger w-100" style={{ width: '100%' }} onClick={() => {
            if(window.confirm('Möchtest du das System wirklich herunterfahren?')){
                axios.post('/control', { command: 'shutdown' });
            }
        }}>
          <PowerOff size={18} /> Herunterfahren
        </button>
      </div>
    </div>
  );
}

function PageTitle() {
  const location = useLocation();
  const titles = {
    '/': 'Dashboard',
    '/control': 'Mäher-Steuerung',
    '/live': 'Live-Radar',
    '/geofence': 'Zonen-Editor',
    '/maps': 'Historie & Karten',
    '/stats': 'Statistiken & Analyse',
    '/database': 'Datenbank-Manager',
    '/logs': 'System Logs',
    '/config': 'System-Einstellungen'
  };
  return <h1 style={{fontSize: '1.8rem', fontWeight: 600}}>{titles[location.pathname] || 'Übersicht'}</h1>;
}

function App() {
  const [mqttStatus, setMqttStatus] = useState(false);
  const [toasts, setToasts] = useState([]);

  const addToast = (type, message) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 6000);
  };

  useEffect(() => {
    socket.on('connect', () => {
      console.log('Socket connected');
    });

    // Pi-Feedback Live-Toasts
    socket.on('pi_feedback', (data) => {
      addToast(data.type, data.message);
    });

    const checkStatus = async () => {
      try {
        const res = await axios.get('/api/status');
        setMqttStatus(res.data.mqtt_connected);
      } catch(e) {}
    }
    
    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => {
      clearInterval(interval);
      socket.off('pi_feedback');
    };
  }, []);

  return (
    <Router>
      <div className="app-container">
        <Sidebar />
        <main className="main-content">
          <header className="flex-between">
            <PageTitle />
            <div className={`badge ${mqttStatus ? 'success' : 'danger'}`}>
              <div 
                className="pulse-dot" 
                style={{
                    width: 8, height: 8, borderRadius: '50%', 
                    background: mqttStatus ? '#3fb950' : '#ff7b72',
                    boxShadow: mqttStatus ? '0 0 10px #3fb950' : '0 0 10px #ff7b72'
                }}
              />
              {mqttStatus ? 'MQTT Verbunden' : 'MQTT Getrennt'}
            </div>
          </header>
          
          <Routes>
            <Route path="/" element={<Dashboard socket={socket} />} />
            <Route path="/control" element={<MowerControl />} />
            <Route path="/live" element={<Live />} />
            <Route path="/maps" element={<Maps />} />
            <Route path="/geofence" element={<Geofence />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/database" element={<DatabaseManager />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/config" element={<Config addToast={addToast} />} />
          </Routes>
        </main>

        {/* Global Toast Container */}
        <div style={{
          position: 'fixed', top: 20, right: 20, zIndex: 9999,
          display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 400
        }}>
          {toasts.map(toast => (
            <div key={toast.id} style={{
              padding: '14px 20px',
              borderRadius: 12,
              background: toast.type === 'success' 
                ? 'linear-gradient(135deg, rgba(46,160,67,0.95), rgba(35,134,54,0.95))'
                : 'linear-gradient(135deg, rgba(218,54,51,0.95), rgba(164,14,11,0.95))',
              border: `1px solid ${toast.type === 'success' ? 'rgba(63,185,80,0.5)' : 'rgba(255,123,114,0.5)'}`,
              color: '#fff',
              fontSize: '0.9rem',
              fontWeight: 500,
              backdropFilter: 'blur(12px)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
              animation: 'slideInRight 0.3s ease-out',
              display: 'flex', alignItems: 'center', gap: 10,
              cursor: 'pointer'
            }} onClick={() => setToasts(prev => prev.filter(t => t.id !== toast.id))}>
              <span style={{fontSize: '1.2rem'}}>{toast.type === 'success' ? '✅' : '❌'}</span>
              {toast.message}
            </div>
          ))}
        </div>
      </div>
    </Router>
  );
}

export default App;
