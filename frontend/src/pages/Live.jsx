import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, Alert } from 'react-bootstrap';
import LiveMapWidget from '../components/LiveMapWidget';
import './Live.css';

const Live = ({ socket }) => {
  const [status, setStatus] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchLiveConfig();

    if (socket) {
      const handleStatusUpdate = (data) => {
        setStatus(data);
      };
      
      socket.on('status_update', handleStatusUpdate);

      return () => {
        socket.off('status_update', handleStatusUpdate);
      };
    }
  }, [socket]);

  const fetchLiveConfig = async () => {
    try {
      const response = await fetch('/api/live_config');
      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }
      setStatus(data.status);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const handleControl = async (command) => {
    try {
      const response = await fetch('/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      });
      const result = await response.json();
      console.log(result);
    } catch (err) {
      console.error('Fehler bei Steuerung:', err);
    }
  };

  if (loading) {
    return <div className="text-center mt-4">Lade Live-Karte...</div>;
  }

  if (error) {
    return <Alert variant="danger">Fehler: {error}</Alert>;
  }

  return (
    <div className="live-page">
      <div className="row">
        {/* Status Informationen */}
        <div className="col-lg-4 col-md-5">
          <h2>Live Status</h2>
          <Card className="status-card mb-3">
            <Card.Body>
              <Card.Title>Aktuelle Position</Card.Title>
              <Card.Text>
                Latitude: <span>{status.lat ? status.lat.toFixed(6) : 'N/A'}</span><br />
                Longitude: <span>{status.lon ? status.lon.toFixed(6) : 'N/A'}</span>
              </Card.Text>
            </Card.Body>
          </Card>

          <Card className="status-card mb-3">
            <Card.Body>
              <Card.Title>GPS Status</Card.Title>
              <Card.Text>
                Status: <span>{status.status_text || 'N/A'}</span><br />
                Satelliten: <span>{status.satellites || 'N/A'}</span><br />
                AGPS: <span>{status.agps_status || 'N/A'}</span><br />
                Aufnahme: <Badge bg={status.is_recording ? 'success' : 'danger'}>
                  {status.is_recording ? 'Läuft' : 'Gestoppt'}
                </Badge><br />
                Letztes Update: <span>{status.last_update || 'N/A'}</span>
              </Card.Text>
            </Card.Body>
          </Card>

          <Card className="status-card">
            <Card.Body>
              <Card.Title>Steuerung</Card.Title>
              <Button variant="success" size="sm" className="me-2 mb-1" onClick={() => handleControl('start_recording')}>
                <i className="fas fa-play"></i> Aufnahme Start
              </Button>
              <Button variant="danger" size="sm" className="me-2 mb-1" onClick={() => handleControl('stop_recording')}>
                <i className="fas fa-stop"></i> Aufnahme Stop
              </Button>
              <Button variant="info" size="sm" className="me-2 mb-1" onClick={() => handleControl('generate_heatmaps')}>
                <i className="fas fa-fire"></i> Heatmaps Generieren
              </Button>
            </Card.Body>
          </Card>

          <Card className="status-card mt-3">
            <Card.Body>
              <Card.Title>Simulator (Chaos-Prinzip)</Card.Title>
              <Card.Text className="text-muted" style={{fontSize: '0.85rem'}}>
                Simuliert einen Mähvorgang innerhalb der in config.py definierten Grundstücksgrenzen.
              </Card.Text>
              <Button variant="outline-success" size="sm" className="me-2 mb-1" onClick={() => handleControl('start_simulator')}>
                <i className="fas fa-robot"></i> Simulator Start
              </Button>
              <Button variant="outline-danger" size="sm" className="mb-1" onClick={() => handleControl('stop_simulator')}>
                <i className="fas fa-power-off"></i> Simulator Stop
              </Button>
            </Card.Body>
          </Card>
        </div>

        {/* Live Karte */}
        <div className="col-lg-8 col-md-7">
          <h2>Live Karte</h2>
          <div style={{ minHeight: '65vh', height: '600px', width: '100%', borderRadius: '8px', border: '1px solid #dee2e6', overflow: 'hidden' }}>
            <LiveMapWidget socket={socket} height="100%" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Live;
