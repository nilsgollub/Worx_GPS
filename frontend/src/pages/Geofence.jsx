import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Polygon, Popup, LayersControl, useMapEvents, Marker } from 'react-leaflet';
import { Save, Trash2, Shield, AlertCircle, MousePointer2, Eraser, Check, Plus, Edit2, XCircle } from 'lucide-react';
import axios from 'axios';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in Leaflet + React
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
let DefaultIcon = L.icon({
    iconUrl: markerIcon,
    shadowUrl: markerShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// Custom Draw and Edit Component
const CustomDrawTool = ({ onFinished, active, editPoints, onEditChange }) => {
    const [points, setPoints] = useState([]);
    const [mousePos, setMousePos] = useState(null);

    // Sync with editPoints if we are in edit mode
    useEffect(() => {
        if (editPoints) {
            setPoints(editPoints);
        } else {
            setPoints([]);
        }
    }, [editPoints]);

    useMapEvents({
        click(e) {
            if (!active || editPoints) return; // Only draw if active and NOT editing existing
            const newPoints = [...points, [e.latlng.lat, e.latlng.lng]];
            setPoints(newPoints);
        },
        mousemove(e) {
            if (!active || points.length === 0 || editPoints) return;
            setMousePos([e.latlng.lat, e.latlng.lng]);
        }
    });

    const handleMarkerDrag = (index, e) => {
        const newPoints = [...points];
        newPoints[index] = [e.target.getLatLng().lat, e.target.getLatLng().lng];
        setPoints(newPoints);
        if (onEditChange) onEditChange(newPoints);
    };

    const reset = () => {
        setPoints([]);
        setMousePos(null);
        if (onFinished) onFinished(null);
    };

    const finish = () => {
        if (points.length < 3) {
            alert("Ein Polygon benötigt mindestens 3 Punkte!");
            return;
        }
        onFinished(points);
        setPoints([]);
        setMousePos(null);
    };

    // If not drawing and not editing and no points, show nothing
    if (!active && !editPoints && points.length === 0) return null;

    return (
        <>
            {/* The polygon being drawn or edited */}
            {points.length > 1 && (
                <Polygon 
                    positions={points} 
                    pathOptions={{ 
                        color: editPoints ? '#3fb950' : '#ff6b6b', 
                        dashArray: editPoints ? '' : '5, 5', 
                        fillOpacity: 0.2 
                    }} 
                />
            )}
            
            {/* Rubber band line when drawing */}
            {active && !editPoints && mousePos && points.length > 0 && (
                <Polygon 
                    positions={[...points, mousePos]} 
                    pathOptions={{ color: '#ff6b6b', weight: 1, dashArray: '2, 5', fillOpacity: 0 }} 
                />
            )}

            {/* Draggable markers for vertices in Edit/Draw mode */}
            {(active || editPoints) && points.map((p, i) => (
                <Marker 
                    key={`${i}-${p[0]}`} 
                    position={p} 
                    draggable={true}
                    eventHandlers={{
                        dragend: (e) => handleMarkerDrag(i, e)
                    }}
                />
            ))}

            {/* Controls Overlay */}
            {(active || editPoints) && (
                <div style={{
                    position: 'absolute', top: '20px', left: '50%', transform: 'translateX(-50%)',
                    zIndex: 1000, display: 'flex', gap: '10px'
                }}>
                    <div className="glass-panel p-2 flex-between gap-3 shadow-lg">
                        <span className="text-small" style={{ color: 'white', fontWeight: 500 }}>
                            {editPoints ? 'Zone bearbeiten' : 'Neue Zone'} ({points.length} Punkte)
                        </span>
                        <button className="btn btn-success" style={{ padding: '6px 15px' }} onClick={finish}>
                            <Check size={16} /> {editPoints ? 'Übernehmen' : 'Fertig'}
                        </button>
                        <button className="btn btn-danger" style={{ padding: '6px 15px' }} onClick={reset}>
                            <XCircle size={16} /> Abbrechen
                        </button>
                    </div>
                </div>
            )}
        </>
    );
};

// Main Geofence Component
const Geofence = () => {
    const [geofences, setGeofences] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedFence, setSelectedFence] = useState(null);
    const [newFenceName, setNewFenceName] = useState('');
    const [mapConfig, setMapConfig] = useState(null);
    const [message, setMessage] = useState({ text: '', type: '' });
    const [isDrawing, setIsDrawing] = useState(false);
    const [isEditing, setIsEditing] = useState(false);

    useEffect(() => {
        fetchGeofences();
        fetchMapConfig();
    }, []);

    const fetchGeofences = async () => {
        try {
            const res = await axios.get('/api/geofences');
            setGeofences(res.data);
            setLoading(false);
        } catch (err) {
            console.error("Fehler beim Laden der Geofences:", err);
            setLoading(false);
        }
    };

    const fetchMapConfig = async () => {
        try {
            const res = await axios.get('/api/live_config');
            setMapConfig(res.data.map_config);
        } catch (err) {
            console.error("Fehler beim Laden der Map-Config:", err);
        }
    };

    const showMessage = (text, type = 'info') => {
        setMessage({ text, type });
        setTimeout(() => setMessage({ text: '', type: '' }), 5000);
    };

    const onActionFinished = (points) => {
        if (!points) {
            setSelectedFence(null);
            setIsDrawing(false);
            setIsEditing(false);
            return;
        }
        
        if (isEditing) {
            setSelectedFence({ ...selectedFence, coordinates: points });
            setIsEditing(false);
            // Auto save updated existing fence? Or let user confirm name?
            // For editing, we usually want to save it directly or keep in selection
        } else {
            setSelectedFence({ coordinates: points, type: 'mow_area' });
            setNewFenceName('Neue Zone ' + (geofences.length + 1));
            setIsDrawing(false);
        }
    };

    const startEditing = (fence) => {
        setSelectedFence(fence);
        setNewFenceName(fence.name);
        setIsEditing(true);
        setIsDrawing(false);
    };

    const saveFence = async () => {
        if (!selectedFence || !newFenceName) return;

        try {
            const res = await axios.post('/api/geofences', {
                id: selectedFence.id, // Include ID if editing
                name: newFenceName,
                type: selectedFence.type,
                coordinates: selectedFence.coordinates
            });
            if (res.data.status === 'success') {
                showMessage(selectedFence.id ? 'Zone aktualisiert!' : 'Geofence gespeichert!', 'success');
                setSelectedFence(null);
                setNewFenceName('');
                fetchGeofences();
            }
        } catch (err) {
            showMessage('Fehler beim Speichern!', 'danger');
        }
    };

    const deleteFence = async (id) => {
        if (!window.confirm('Diese Zone wirklich löschen?')) return;
        try {
            await axios.delete(`/api/geofences/${id}`);
            showMessage('Zone gelöscht.', 'warning');
            fetchGeofences();
        } catch (err) {
            showMessage('Fehler beim Löschen!', 'danger');
        }
    };

    if (loading || !mapConfig) {
        return <div className="p-5 text-center">Lade Geofencing-Editor...</div>;
    }

    return (
        <div className="flex-column gap-4" style={{ height: 'calc(100vh - 150px)' }}>
            {message.text && (
                <div className={`badge ${message.type}`} style={{ 
                    position: 'fixed', top: '20px', right: '20px', zIndex: 2000,
                    padding: '12px', boxShadow: '0 4px 15px rgba(0,0,0,0.5)' 
                }}>
                    <AlertCircle size={16} /> {message.text}
                </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '24px', height: '100%' }}>
                {/* Map Section */}
                <div className="glass-panel" style={{ overflow: 'hidden', position: 'relative' }}>
                    <MapContainer
                        center={[mapConfig.initial_lat, mapConfig.initial_lon]}
                        zoom={mapConfig.initial_zoom}
                        style={{ height: '100%', width: '100%', cursor: (isDrawing || isEditing) ? 'crosshair' : 'grab' }}
                    >
                        <LayersControl position="topright">
                            <LayersControl.BaseLayer checked name="Google Satellite">
                                <TileLayer url={mapConfig.satellite_tiles} attribution={mapConfig.satellite_attr} maxZoom={20} />
                            </LayersControl.BaseLayer>
                            <LayersControl.BaseLayer name="OpenStreetMap">
                                <TileLayer url={mapConfig.osm_tiles} attribution={mapConfig.osm_attr} />
                            </LayersControl.BaseLayer>
                        </LayersControl>

                        {/* Existing Fences (Hidden when editing THIS fence) */}
                        {geofences.filter(f => selectedFence?.id !== f.id).map(fence => (
                            <Polygon 
                                key={fence.id} 
                                positions={fence.coordinates}
                                pathOptions={{ 
                                    color: fence.type === 'forbidden_area' ? '#ff6b6b' : '#2f81f7', 
                                    fillColor: fence.type === 'forbidden_area' ? '#ff6b6b' : '#2f81f7', 
                                    fillOpacity: 0.25, 
                                    weight: 2 
                                }}
                            >
                                <Popup><strong>{fence.name}</strong> ({fence.type === 'mow_area' ? 'Erlaubt' : 'Verboten'})</Popup>
                            </Polygon>
                        ))}

                        <CustomDrawTool 
                            active={isDrawing} 
                            editPoints={isEditing ? selectedFence.coordinates : null}
                            onFinished={onActionFinished} 
                            onEditChange={(pts) => setSelectedFence({...selectedFence, coordinates: pts})}
                        />
                    </MapContainer>
                </div>

                {/* Sidebar */}
                <div className="flex-column gap-4">
                    <div className="glass-panel p-4" style={{ height: 'fit-content' }}>
                        <h3 className="mb-3" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <Shield size={20} color="#2f81f7" /> Editor
                        </h3>
                        
                        {!isDrawing && !selectedFence && (
                            <button className="btn btn-primary w-100" onClick={() => setIsDrawing(true)}>
                                <Plus size={18} /> Neue Zone zeichnen
                            </button>
                        )}

                        {selectedFence && !isDrawing && !isEditing && (
                            <div className="flex-column gap-3 mt-2">
                                <div className="flex-column gap-2 mb-2">
                                    <label className="text-small text-muted">Zonen-Typ</label>
                                    <div className="flex gap-2">
                                        <button 
                                            className={`btn flex-1 ${selectedFence.type === 'mow_area' ? 'btn-primary' : 'glass-card'}`}
                                            onClick={() => setSelectedFence({...selectedFence, type: 'mow_area'})}
                                        >
                                            Erlaubt
                                        </button>
                                        <button 
                                            className={`btn flex-1 ${selectedFence.type === 'forbidden_area' ? 'btn-danger' : 'glass-card'}`}
                                            onClick={() => setSelectedFence({...selectedFence, type: 'forbidden_area'})}
                                        >
                                            Verboten
                                        </button>
                                    </div>
                                </div>
                                <label className="text-small text-muted">Zonen-Name</label>
                                <input 
                                    className="glass-card w-100" 
                                    style={{ background: 'rgba(255,255,255,0.05)', color: 'white', border: '1px solid var(--panel-border)', padding: '10px' }}
                                    value={newFenceName}
                                    onChange={(e) => setNewFenceName(e.target.value)}
                                />
                                <div className="flex-between gap-2 mt-2">
                                    <button className="btn btn-success flex-1" onClick={saveFence}>
                                        <Save size={18} /> Speichern
                                    </button>
                                    <button className="btn btn-primary" onClick={() => setIsEditing(true)} title="Punkte bearbeiten">
                                        <Edit2 size={18} />
                                    </button>
                                    <button className="btn btn-danger" onClick={() => setSelectedFence(null)}>
                                        <Trash2 size={18} />
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="glass-panel p-4 flex-column gap-3" style={{ flex: 1, overflowY: 'auto' }}>
                        <h4 className="text-small">Zonen ({geofences.length})</h4>
                        {geofences.length === 0 ? (
                            <p className="text-small text-muted italic mt-4 text-center">Keine Zonen definiert.</p>
                        ) : (
                            geofences.map(fence => (
                                <div key={fence.id} className="glass-card flex-between" style={{ padding: '12px' }}>
                                    <div style={{ overflow: 'hidden', cursor: 'pointer' }} onClick={() => startEditing(fence)}>
                                        <div style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                            {fence.name} {fence.type === 'forbidden_area' && <span style={{ color: '#ff6b6b', fontSize: '0.75rem' }}>(Verboten)</span>}
                                        </div>
                                        <div className="text-small text-muted">{fence.coordinates.length} Eckpunkte</div>
                                    </div>
                                    <div className="flex gap-2">
                                        <button className="btn glass-card" style={{ padding: '6px' }} onClick={() => startEditing(fence)}>
                                            <Edit2 size={16} />
                                        </button>
                                        <button className="btn btn-danger" style={{ padding: '6px' }} onClick={(e) => { e.stopPropagation(); deleteFence(fence.id); }}>
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Geofence;
