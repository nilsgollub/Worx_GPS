# kalman_filter.py
import numpy as np

class GpsKalmanFilter:
    """
    Ein 2D Kalman-Filter zur Glättung von GPS-Koordinaten.
    Er modelliert die Position (Lat/Lon) und die Geschwindigkeit
    mit Fokus auf die geringe Geschwindigkeit eines Mähroboters.
    """
    def __init__(self, process_noise=1e-7, measurement_noise=1e-5):
        """
        Initialisiert den Filter.
        
        Args:
            process_noise (Q): Erwartetes Rauschen in der Eigenbewegung (Mäher).
            measurement_noise (R): Erwartetes Rauschen der GPS-Hardware.
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

    def update(self, lat, lon, timestamp, hdop=None, imu_yaw=None):
        """
        Aktualisiert den Filter mit einer neuen Messung.
        """
        if not self.initialized:
            self.x = np.array([lat, lon, 0.0, 0.0])
            self.last_timestamp = timestamp
            self.initialized = True
            return lat, lon

        dt = timestamp - self.last_timestamp
        if dt <= 0:
            return self.x[0], self.x[1]

        # --- 1. Prediction ---
        self.F[0, 2] = dt
        self.F[1, 3] = dt
        self.x = np.dot(self.F, self.x)
        self.P = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q

        # -- Sensor Fusion: IMU Ausrichtung ---
        # Wenn imu_yaw (0-360 Grad) verfügbar ist, richten wir den internen
        # Geschwindigkeitsvektor an der bekannten Orientierung aus
        if imu_yaw is not None:
            # Einfaches Modell: Geschwindigkeit v bestimmen und durch Yaw korrigieren
            v = np.sqrt(self.x[2]**2 + self.x[3]**2)
            if v > 0.1: # Nur wenn wir überhaupt fahren
                import math
                yaw_rad = math.radians(imu_yaw)
                # Yaw in Navigationskoordinaten: 0=N, 90=E -> lat=N, lon=E
                # Dies ist eine Heuristik zur Fusionierung der Richtungsvektoren
                v_N_corrected = v * math.cos(yaw_rad)
                v_E_corrected = v * math.sin(yaw_rad)
                # Dämpfe die Korrektur etwas (Complimentary Filter Ansatz im Zustand)
                alpha = 0.5 
                self.x[2] = self.x[2] * (1-alpha) + v_N_corrected * alpha
                self.x[3] = self.x[3] * (1-alpha) + v_E_corrected * alpha

        # --- 2. Measurement ---
        current_R = self.R
        if hdop is not None:
             current_R = self.R * (hdop ** 2)

        z = np.array([lat, lon])
        y = z - np.dot(self.H, self.x)
        S = np.dot(self.H, np.dot(self.P, self.H.T)) + current_R
        K = np.dot(np.dot(self.P, self.H.T), np.linalg.inv(S))
        
        self.x = self.x + np.dot(K, y)
        self.P = self.P - np.dot(np.dot(K, self.H), self.P)

        self.last_timestamp = timestamp
        return self.x[0], self.x[1]

    def reset(self):
        self.initialized = False
        self.last_timestamp = None
        self.x = np.array([0.0, 0.0, 0.0, 0.0])
        self.P = np.eye(4) * 1.0
