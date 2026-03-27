import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, LayersControl } from 'react-leaflet';
import { Radio, Signal, Satellite, Battery, MapPin, Navigation } from 'lucide-react';
import { socket } from '../App';
import axios from 'axios';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
let DefaultIcon = L.icon({
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// Custom Mower Icon
const mowerIcon = L.icon({
    iconUrl: './worx.png',
    iconSize: [25, 32],
    iconAnchor: [12.5, 16],
    popupAnchor: [0, -18]
});

const Live = () => {
    const [mowerStatus, setMowerStatus] = useState(null);
    const [path, setPath] = useState([]);
    const [mapConfig, setMapConfig] = useState(null);
    const [geofences, setGeofences] = useState([]);

    useEffect(() => {
        // Initialen Status laden
        axios.get('/api/status').then(res => {
            if (res.data.status) {
                setMowerStatus(res.data.status);
                if (res.data.status.lat && res.data.status.lon) {
                    setPath(prev => [...prev, [res.data.status.lat, res.data.status.lon]]);
                }
            }
        });

        // Map Config laden
        axios.get('/api/live_config').then(res => {
            setMapConfig(res.data.map_config);
        });

        // Geofences laden (für den Hintergrund)
        axios.get('/api/geofences').then(res => {
            setGeofences(res.data);
        });

        // Socket.IO Listener für Echtzeit-Updates
        const handleStatusUpdate = (data) => {
            setMowerStatus(data);
            if (data.lat && data.lon) {
                // Nur hinzufügen, wenn sich die Position signifikant geändert hat
                setPath(prev => {
                    if (prev.length === 0) return [[data.lat, data.lon]];
                    const last = prev[prev.length - 1];
                    if (Math.abs(last[0] - data.lat) > 0.000001 || Math.abs(last[1] - data.lon) > 0.000001) {
                        return [...prev, [data.lat, data.lon]];
                    }
                    return prev;
                });
            }
        };

        socket.on('status_update', handleStatusUpdate);

        return () => {
            socket.off('status_update', handleStatusUpdate);
        };
    }, []);

    if (!mapConfig) return <div className="p-5 text-center">Initialisiere Live-Radar...</div>;

    const currentPos = mowerStatus?.lat && mowerStatus?.lon ? [mowerStatus.lat, mowerStatus.lon] : [mapConfig.initial_lat, mapConfig.initial_lon];

    return (
        <div className="flex-column gap-4" style={{ height: 'calc(100vh - 150px)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '24px', height: '100%' }}>
                
                {/* Map Section */}
                <div className="glass-panel" style={{ overflow: 'hidden', position: 'relative' }}>
                    <MapContainer
                        center={currentPos}
                        zoom={mapConfig.initial_zoom}
                        style={{ height: '100%', width: '100%' }}
                    >
                        <LayersControl position="topright">
                            <LayersControl.BaseLayer checked name="Google Satellite">
                                <TileLayer url={mapConfig.satellite_tiles} attribution={mapConfig.satellite_attr} maxZoom={20} />
                            </LayersControl.BaseLayer>
                            <LayersControl.BaseLayer name="OpenStreetMap">
                                <TileLayer url={mapConfig.osm_tiles} attribution={mapConfig.osm_attr} />
                            </LayersControl.BaseLayer>
                        </LayersControl>

                        {/* Geofences im Hintergrund */}
                        {geofences.map(fence => (
                            <Polyline 
                                key={fence.id} 
                                positions={fence.coordinates}
                                pathOptions={{ 
                                    color: fence.type === 'forbidden_area' ? 'rgba(255, 107, 107, 0.3)' : 'rgba(47, 129, 247, 0.2)', 
                                    weight: 1,
                                    fill: true,
                                    fillOpacity: 0.1
                                }}
                            />
                        ))}

                        {/* Mäh-Pfad (Verlauf) */}
                        {path.length > 1 && (
                            <Polyline 
                                positions={path} 
                                pathOptions={{ color: '#3fb950', weight: 3, opacity: 0.8 }} 
                            />
                        )}

                        {/* Mäher-Marker */}
                        {mowerStatus?.lat && (
                            <Marker position={[mowerStatus.lat, mowerStatus.lon]} icon={mowerIcon}>
                                <Popup>
                                    <strong>Mäher-Position</strong><br />
                                    {mowerStatus.status_text}<br />
                                    {new Date().toLocaleTimeString()}
                                </Popup>
                            </Marker>
                        )}
                    </MapContainer>

                    {/* Overlay Status */}
                    <div style={{
                        position: 'absolute', bottom: '20px', left: '20px', zIndex: 1000,
                        pointerEvents: 'none'
                    }}>
                        <div className="glass-panel p-3 shadow-lg flex-column gap-2">
                             <div className="flex-between gap-4">
                                <span className="text-small text-muted">Status:</span>
                                <span className="text-small bold" style={{color: '#2f81f7'}}>{mowerStatus?.status_text || 'Warte auf Daten...'}</span>
                             </div>
                             <div className="flex-between gap-4">
                                <span className="text-small text-muted">GPS-FIX:</span>
                                <span className={`badge ${mowerStatus?.gps_fix?.includes('SPS') ? 'success' : 'warning'}`}>{mowerStatus?.gps_fix || 'N/A'}</span>
                             </div>
                        </div>
                    </div>
                </div>

                {/* Info Sidebar */}
                <div className="flex-column gap-4">
                    <div className="glass-panel p-4 flex-column gap-3">
                        <h3 className="flex-between">
                            Telemetrie <Radio size={18} className="pulse-dot" style={{background:'none', color:'#2f81f7'}} />
                        </h3>
                        
                        <div className="flex-column gap-3">
                            <div className="glass-card p-3 flex-between">
                                <div className="flex gap-2 text-muted text-small"><Satellite size={16} /> Satelliten</div>
                                <div className="bold">{mowerStatus?.satellites || 0}</div>
                            </div>
                            
                            <div className="glass-card p-3 flex-between">
                                <div className="flex gap-2 text-muted text-small"><Signal size={16} /> WiFi Signal</div>
                                <div className="bold">{mowerStatus?.wifi || 0} dBm</div>
                            </div>

                            <div className="glass-card p-3 flex-between">
                                <div className="flex gap-2 text-muted text-small"><Navigation size={16} /> HDOP</div>
                                <div className="bold">{mowerStatus?.hdop || 'N/A'}</div>
                            </div>
                        </div>
                    </div>

                    <div className="glass-panel p-4" style={{flex: 1}}>
                        <h4 className="text-small mb-3">Aufzeichnung</h4>
                        <div className="text-small text-muted mb-2">Punkte in aktueller Ansicht:</div>
                        <div className="bold text-large mb-4" style={{fontSize: '2rem'}}>{path.length}</div>
                        
                        <button className="btn glass-card w-100 mb-2" onClick={() => setPath([])}>
                            Spur löschen
                        </button>
                        <p className="text-micro text-muted italic mt-2">
                            Hinweis: Der Pfad im Live-Radar wird nur clientseitig gehalten und nicht in der Historie gespeichert. 🛰️
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Live;
