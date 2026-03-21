import React, { useState, useEffect } from 'react';

import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';

import { RadioTower, Map, Activity, Settings, Server, Menu, X, Power, PowerOff } from 'lucide-react';

import Dashboard from './pages/Dashboard';

import Maps from './pages/Maps';

import Config from './pages/Config';

import Stats from './pages/Stats';

import { io } from 'socket.io-client';

import axios from 'axios';



// Update with correct port matching backend .env later if needed

export const API_URL = window.location.hostname === 'localhost' ? 'http://localhost:5001' : `http://${window.location.hostname}:5001`;

export const socket = io(API_URL);



axios.defaults.baseURL = API_URL;



function Sidebar() {

  const location = useLocation();



  const links = [

    { to: '/', icon: <Activity size={20} />, label: 'Dashboard' },

    { to: '/maps', icon: <Map size={20} />, label: 'Karten & Live' },

    { to: '/stats', icon: <RadioTower size={20} />, label: 'Statistiken' },

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



function App() {

  const [mqttStatus, setMqttStatus] = useState(false);



  useEffect(() => {

    socket.on('connect', () => {

      console.log('Socket connected');

    });



    const checkStatus = async () => {

      try {

        const res = await axios.get('/api/status');

        setMqttStatus(res.data.mqtt_connected);

      } catch(e) {}

    }

    

    checkStatus();

    const interval = setInterval(checkStatus, 5000);

    return () => clearInterval(interval);

  }, []);



  return (

    <Router>

      <div className="app-container">

        <Sidebar />

        <main className="main-content">

          <header className="flex-between">

            <h1 style={{fontSize: '1.8rem', fontWeight: 600}}>

               Übersicht

            </h1>

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

            <Route path="/maps" element={<Maps />} />

            <Route path="/stats" element={<Stats />} />

            <Route path="/config" element={<Config />} />

          </Routes>

        </main>

      </div>

    </Router>

  );

}



export default App;

