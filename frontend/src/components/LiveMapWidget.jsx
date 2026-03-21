import React, { useState, useEffect, useRef } from 'react';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import 'leaflet-rotatedmarker';
import axios from 'axios';

// Fix für Leaflet default icons
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const LiveMapWidget = ({ socket, height = '400px' }) => {
  const [status, setStatus] = useState({});
  const [mapConfig, setMapConfig] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markerRef = useRef(null);
  const predictionLineRef = useRef(null);
  const interpolationTimerRef = useRef(null);
  const positionHistoryRef = useRef([]);

  // Konfiguration für Pfadvorhersage
  const PREDICTION_SECONDS = 8;
  const INTERPOLATION_INTERVAL = 100;
  const HISTORY_SIZE = 5;

  useEffect(() => {
    fetchLiveConfig();

    if (socket) {
      const handleStatusUpdate = (data) => {
        setStatus(data);
        if (data && data.lat !== undefined && data.lon !== undefined) {
          updateMap(data.lat, data.lon);
        }
      };

      socket.on('status_update', handleStatusUpdate);

      return () => {
        socket.off('status_update', handleStatusUpdate);
      };
    }
  }, [socket]);

  useEffect(() => {
    return () => {
      if (interpolationTimerRef.current) {
        clearInterval(interpolationTimerRef.current);
      }
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  const fetchLiveConfig = async () => {
    try {
      const response = await axios.get('/api/live_config');
      const data = response.data;
      if (data.error) {
        throw new Error(data.error);
      }
      setStatus(data.status);
      setMapConfig(data.map_config);
      setLoading(false);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  const calculateBearing = (lat1, lon1, lat2, lon2) => {
    const dLon = (lon2 - lon1) * Math.PI / 180;
    lat1 = lat1 * Math.PI / 180;
    lat2 = lat2 * Math.PI / 180;
    const y = Math.sin(dLon) * Math.cos(lat2);
    const x = Math.cos(lat1) * Math.sin(lat2) -
      Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
    let brng = Math.atan2(y, x) * 180 / Math.PI;
    brng = (brng + 360) % 360;
    return brng;
  };

  const calculateVelocityAndDirection = () => {
    if (positionHistoryRef.current.length < 2) return { speed: 0, bearing: 0 };
    
    const recent = positionHistoryRef.current.slice(-2);
    const dt = (recent[1].timestamp - recent[0].timestamp) / 1000;
    
    if (dt === 0) return { speed: 0, bearing: 0 };
    
    const distance = recent[0].latlng.distanceTo(recent[1].latlng);
    const speed = distance / dt;
    
    const bearing = calculateBearing(
      recent[0].latlng.lat, recent[0].latlng.lng,
      recent[1].latlng.lat, recent[1].latlng.lng
    );
    
    return { speed, bearing };
  };

  const calculateDestinationPoint = (lat, lon, bearing, distance) => {
    const R = 6371e3;
    const angularDistance = distance / R;
    const bearingRad = bearing * Math.PI / 180;
    const lat1 = lat * Math.PI / 180;
    const lon1 = lon * Math.PI / 180;
    
    const lat2 = Math.asin(
      Math.sin(lat1) * Math.cos(angularDistance) +
      Math.cos(lat1) * Math.sin(angularDistance) * Math.cos(bearingRad)
    );
    
    const lon2 = lon1 + Math.atan2(
      Math.sin(bearingRad) * Math.sin(angularDistance) * Math.cos(lat1),
      Math.cos(angularDistance) - Math.sin(lat1) * Math.sin(lat2)
    );
    
    return {
      lat: lat2 * 180 / Math.PI,
      lng: lon2 * 180 / Math.PI
    };
  };

  const updatePredictionLine = (currentLatLng, speed, bearing) => {
    if (predictionLineRef.current && mapInstanceRef.current) {
      mapInstanceRef.current.removeLayer(predictionLineRef.current);
      predictionLineRef.current = null;
    }
    
    if (speed < 0.1 || !mapInstanceRef.current) return;
    
    const predictionDistance = speed * PREDICTION_SECONDS;
    const predictionPoints = [];
    
    for (let i = 1; i <= 10; i++) {
      const distance = (predictionDistance / 10) * i;
      const point = calculateDestinationPoint(currentLatLng.lat, currentLatLng.lng, bearing, distance);
      predictionPoints.push([point.lat, point.lng]);
    }
    
    predictionLineRef.current = L.polyline(predictionPoints, {
      color: '#ff6b6b',
      weight: 3,
      opacity: 0.6,
      dashArray: '10, 5'
    }).addTo(mapInstanceRef.current);
  };

  const startInterpolation = () => {
    if (interpolationTimerRef.current) {
      clearInterval(interpolationTimerRef.current);
    }
    
    interpolationTimerRef.current = setInterval(() => {
      if (positionHistoryRef.current.length < 2 || !markerRef.current) return;
      
      const now = Date.now();
      const recent = positionHistoryRef.current.slice(-2);
      const timeSinceLastUpdate = now - recent[1].timestamp;
      const updateInterval = recent[1].timestamp - recent[0].timestamp;
      
      if (timeSinceLastUpdate < updateInterval) {
        const progress = timeSinceLastUpdate / updateInterval;
        const interpolatedLat = recent[0].latlng.lat + (recent[1].latlng.lat - recent[0].latlng.lat) * progress;
        const interpolatedLng = recent[0].latlng.lng + (recent[1].latlng.lng - recent[0].latlng.lng) * progress;
        
        const interpolatedLatLng = L.latLng(interpolatedLat, interpolatedLng);
        markerRef.current.setLatLng(interpolatedLatLng);
        
        const { speed, bearing } = calculateVelocityAndDirection();
        updatePredictionLine(interpolatedLatLng, speed, bearing);
      }
    }, INTERPOLATION_INTERVAL);
  };

  const updateMap = (lat, lon) => {
    if (!mapInstanceRef.current || lat === undefined || lon === undefined) return;

    const newLatLng = L.latLng(lat, lon);
    const timestamp = Date.now();
    
    positionHistoryRef.current.push({ latlng: newLatLng, timestamp });
    if (positionHistoryRef.current.length > HISTORY_SIZE) {
      positionHistoryRef.current.shift();
    }

    const mowerIcon = L.icon({
      iconUrl: './worx.png',
      iconSize: [25, 32],
      iconAnchor: [12.5, 16],
      popupAnchor: [0, -18]
    });

    if (!markerRef.current) {
      markerRef.current = L.marker([lat, lon], {
        icon: mowerIcon,
        rotationAngle: 0,
        rotationOrigin: 'center center'
      }).addTo(mapInstanceRef.current).bindPopup("Aktuelle Position").openPopup();
      
      startInterpolation();
    } else {
      const { speed } = calculateVelocityAndDirection();
      let bearing = 0;
      
      if (positionHistoryRef.current.length >= 2) {
        const recent = positionHistoryRef.current.slice(-2);
        if (recent[0].latlng.lat !== newLatLng.lat || recent[0].latlng.lng !== newLatLng.lng) {
          bearing = calculateBearing(recent[0].latlng.lat, recent[0].latlng.lng, newLatLng.lat, newLatLng.lng);
          if (markerRef.current.setRotationAngle) {
            markerRef.current.setRotationAngle(bearing);
          }
        }
      }
      
      markerRef.current.setLatLng(newLatLng);
      
      if (positionHistoryRef.current.length >= 2) {
        const { bearing: currentBearing } = calculateVelocityAndDirection();
        updatePredictionLine(newLatLng, speed, currentBearing);
      }
      
      if (!mapInstanceRef.current.getBounds().contains(newLatLng)) {
        mapInstanceRef.current.setView(newLatLng);
      }
    }
  };

  useEffect(() => {
    if (!loading && mapConfig.initial_lat && mapRef.current && !mapInstanceRef.current) {
      mapInstanceRef.current = L.map(mapRef.current).setView(
        [mapConfig.initial_lat, mapConfig.initial_lon], 
        mapConfig.initial_zoom
      );

      const osmLayer = L.tileLayer(mapConfig.osm_tiles, {
        maxZoom: mapConfig.max_zoom,
        maxNativeZoom: 19,
        attribution: mapConfig.osm_attr
      });

      const satelliteLayer = L.tileLayer(mapConfig.satellite_tiles, {
        maxZoom: mapConfig.max_zoom,
        maxNativeZoom: 20,
        attribution: mapConfig.satellite_attr
      }).addTo(mapInstanceRef.current);

      const baseLayers = {
        "OpenStreetMap": osmLayer,
        "Google Satellite": satelliteLayer
      };
      L.control.layers(baseLayers).addTo(mapInstanceRef.current);

      if (status.lat && status.lon) {
        updateMap(status.lat, status.lon);
      }
    }
  }, [loading, mapConfig]);

  if (loading) {
    return <div className="text-center mt-4 p-5 border rounded" style={{ backgroundColor: '#f8f9fa' }}>Lade Live-Karte...</div>;
  }

  if (error) {
    return <div className="alert alert-danger">Fehler: {error}</div>;
  }

  return (
    <div ref={mapRef} style={{ height: height, width: '100%', borderRadius: '8px', border: '1px solid #dee2e6', zIndex: 1 }}></div>
  );
};

export default LiveMapWidget;
