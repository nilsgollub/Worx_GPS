# kalman_filter.py
import numpy as np
import math
import logging

logger = logging.getLogger(__name__)


class GpsKalmanFilter:
    """
    Ein 2D Kalman-Filter zur Glättung von GPS-Koordinaten.
    Er modelliert die Position (Lat/Lon) und die Geschwindigkeit
    mit Fokus auf die geringe Geschwindigkeit eines Mähroboters.
    
    Unterstützt Dead Reckoning: Zwischen GPS-Fixes wird die Position
    mithilfe der IMU-Richtung (Yaw) und geschätzter Geschwindigkeit
    weitergeführt, was besonders in Kurven hilft.
    """
    def __init__(self, process_noise=1e-7, measurement_noise=1e-5, dead_reckoning_enabled=True):
        """
        Initialisiert den Filter.
        
        Args:
            process_noise (Q): Erwartetes Rauschen in der Eigenbewegung (Mäher).
            measurement_noise (R): Erwartetes Rauschen der GPS-Hardware.
            dead_reckoning_enabled: Aktiviert Dead Reckoning zwischen GPS-Fixes.
        """
        # Zustandsvektor [lat, lon, v_lat, v_lon]
        self.x = np.array([0.0, 0.0, 0.0, 0.0])
        
        # Kovarianzmatrix (Unsicherheit)
        self.P = np.eye(4) * 1.0
        
        # Übergangsmatrix (Modell: Position + Geschwindigkeit * dt)
        # dt wird bei jedem 'predict' aktualisiert
        self.F = np.eye(4)
        
        # Messmatrix (Wir messen nur Position, nicht Geschwindigkeit)
        self.H = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0]
        ])
        
        # Rausch-Matrizen
        self.Q = np.eye(4) * process_noise
        self.R = np.eye(2) * measurement_noise
        
        self.initialized = False
        self.last_timestamp = None
        
        # Dead Reckoning
        self.dead_reckoning_enabled = dead_reckoning_enabled
        self._last_imu_yaw = None
        self._estimated_speed = 0.0  # Geschätzte Geschwindigkeit in Grad/s (lat/lon)
        self._speed_history = []     # Für gleitenden Durchschnitt der Geschwindigkeit
        self._max_speed_history = 10

    def update(self, lat, lon, timestamp, hdop=None, imu_yaw=None):
        """
        Aktualisiert den Filter mit einer neuen GPS-Messung.
        
        Args:
            lat, lon: GPS-Koordinaten
            timestamp: Unix-Zeitstempel
            hdop: Horizontal Dilution of Precision (optional)
            imu_yaw: Yaw-Winkel vom IMU in Grad (0=Nord, 90=Ost) (optional)
        
        Returns:
            (filtered_lat, filtered_lon)
        """
        if not self.initialized:
            self.x = np.array([lat, lon, 0.0, 0.0])
            self.last_timestamp = timestamp
            self.initialized = True
            if imu_yaw is not None:
                self._last_imu_yaw = imu_yaw
            return lat, lon

        dt = timestamp - self.last_timestamp
        if dt <= 0:
            return self.x[0], self.x[1]

        # --- 1. Prediction ---
        self.F[0, 2] = dt
        self.F[1, 3] = dt
        
        # Dead Reckoning: Wenn IMU-Yaw verfügbar, nutze Richtung für bessere Prediction
        if self.dead_reckoning_enabled and imu_yaw is not None:
            self._apply_dead_reckoning(dt, imu_yaw)
        
        self.x = np.dot(self.F, self.x)
        self.P = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q

        # --- 2. Measurement Update ---
        current_R = self.R
        if hdop is not None:
            try:
                hdop_val = float(hdop)
                current_R = self.R * (hdop_val ** 2)
            except (ValueError, TypeError):
                pass

        z = np.array([lat, lon])
        y = z - np.dot(self.H, self.x)
        S = np.dot(self.H, np.dot(self.P, self.H.T)) + current_R
        K = np.dot(np.dot(self.P, self.H.T), np.linalg.inv(S))
        
        self.x = self.x + np.dot(K, y)
        self.P = self.P - np.dot(np.dot(K, self.H), self.P)

        # Geschwindigkeit für Dead Reckoning aktualisieren
        self._update_speed_estimate()
        
        # IMU-Yaw merken
        if imu_yaw is not None:
            self._last_imu_yaw = imu_yaw

        self.last_timestamp = timestamp
        return self.x[0], self.x[1]

    def predict_dead_reckoning(self, timestamp, imu_yaw=None):
        """
        Führt NUR eine Prediction durch (ohne GPS-Messung).
        Nützlich, wenn kein GPS-Fix verfügbar ist, aber IMU-Daten vorhanden sind.
        
        Args:
            timestamp: Aktueller Zeitstempel
            imu_yaw: Aktuelle Yaw-Orientierung (optional)
        
        Returns:
            (predicted_lat, predicted_lon) oder None wenn nicht initialisiert
        """
        if not self.initialized or self.last_timestamp is None:
            return None
        
        dt = timestamp - self.last_timestamp
        if dt <= 0 or dt > 5.0:  # Max 5s Dead Reckoning
            return None
        
        if not self.dead_reckoning_enabled:
            return self.x[0], self.x[1]
        
        # Prediction mit Dead Reckoning
        self.F[0, 2] = dt
        self.F[1, 3] = dt
        
        if imu_yaw is not None:
            self._apply_dead_reckoning(dt, imu_yaw)
        
        self.x = np.dot(self.F, self.x)
        # Erhöhe Unsicherheit stärker bei Dead Reckoning (kein GPS-Update)
        self.P = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q * 3.0
        
        self.last_timestamp = timestamp
        return self.x[0], self.x[1]

    def _apply_dead_reckoning(self, dt, imu_yaw):
        """
        Nutzt IMU-Yaw, um den Geschwindigkeitsvektor in der Prediction zu korrigieren.
        
        Statt blind die letzte Geschwindigkeit fortzuschreiben (was gerade Linien erzwingt),
        richten wir den Geschwindigkeitsvektor an der tatsächlichen Fahrtrichtung aus.
        Das verhindert die "Verrundung" in Kurven.
        """
        # Aktuelle geschätzte Geschwindigkeit (Betrag)
        v = math.sqrt(self.x[2]**2 + self.x[3]**2)
        
        if v < 1e-9:  # Mäher steht still
            return
        
        # Yaw in Navigationskoordinaten: 0=Nord, 90=Ost
        yaw_rad = math.radians(imu_yaw)
        
        # Geschwindigkeitskomponenten aus Yaw berechnen
        # lat = Nord-Süd (cos), lon = Ost-West (sin)
        v_lat_imu = v * math.cos(yaw_rad)
        v_lon_imu = v * math.sin(yaw_rad)
        
        # Stärke der IMU-Korrektur (0.0 = nur GPS, 1.0 = nur IMU)
        # Bei Richtungsänderung (Kurve) IMU stärker gewichten
        if self._last_imu_yaw is not None:
            yaw_diff = abs(imu_yaw - self._last_imu_yaw)
            if yaw_diff > 180:
                yaw_diff = 360 - yaw_diff
            # Bei großem Yaw-Unterschied: IMU stärker gewichten (Kurve!)
            alpha = min(0.3 + (yaw_diff / 90.0) * 0.4, 0.7)
        else:
            alpha = 0.3
        
        # Complementary Filter: Mische GPS-Geschwindigkeit mit IMU-Richtung
        self.x[2] = self.x[2] * (1 - alpha) + v_lat_imu * alpha
        self.x[3] = self.x[3] * (1 - alpha) + v_lon_imu * alpha
        
        self._last_imu_yaw = imu_yaw

    def _update_speed_estimate(self):
        """Aktualisiert die geschätzte Geschwindigkeit (gleitender Durchschnitt)."""
        v = math.sqrt(self.x[2]**2 + self.x[3]**2)
        self._speed_history.append(v)
        if len(self._speed_history) > self._max_speed_history:
            self._speed_history.pop(0)
        self._estimated_speed = sum(self._speed_history) / len(self._speed_history)

    def reset(self):
        self.initialized = False
        self.last_timestamp = None
        self.x = np.array([0.0, 0.0, 0.0, 0.0])
        self.P = np.eye(4) * 1.0
        self._last_imu_yaw = None
        self._estimated_speed = 0.0
        self._speed_history = []
