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

    def update(self, lat, lon, timestamp, hdop=None):
        """
        Aktualisiert den Filter mit einer neuen GPS-Messung.
        
        Args:
            lat: Gemessene Breite.
            lon: Gemessene Länge.
            timestamp: Zeitstempel der Messung.
            hdop: Horizontal Dilution of Precision (Genauigkeits-Indikator).
        """
        if not self.initialized:
            self.x = np.array([lat, lon, 0.0, 0.0])
            self.last_timestamp = timestamp
            self.initialized = True
            return lat, lon

        dt = timestamp - self.last_timestamp
        if dt <= 0:
            return self.x[0], self.x[1]

        # --- 1. Prediction (Vorhersage) ---
        # F-Matrix mit dt aktualisieren [1 0 dt 0; 0 1 0 dt; 0 0 1 0; 0 0 0 1]
        self.F[0, 2] = dt
        self.F[1, 3] = dt
        
        # Neuer Zustand vorherberechnen
        self.x = np.dot(self.F, self.x)
        # Fehlerkovarianz aktualisieren
        self.P = np.dot(np.dot(self.F, self.P), self.F.T) + self.Q

        # --- 2. Measurement Adjustment (HDOP Berücksichtigung) ---
        # Wenn HDOP vorhanden ist, passen wir das Messrauschen (R) dynamisch an.
        # Hoher HDOP -> Höheres Rauschen -> Filter vertraut GPS weniger.
        current_R = self.R
        if hdop is not None:
             # Quadratischer Einfluss von HDOP auf das Vertrauen
             current_R = self.R * (hdop ** 2)

        # --- 3. Correction (Korrektur durch Messung) ---
        z = np.array([lat, lon])
        y = z - np.dot(self.H, self.x) # Messabweichung (Residuum)
        S = np.dot(self.H, np.dot(self.P, self.H.T)) + current_R # Systemunsicherheit
        K = np.dot(np.dot(self.P, self.H.T), np.linalg.inv(S)) # Kalman-Gain
        
        # Zustand und Kovarianz mit Messung korrigieren
        self.x = self.x + np.dot(K, y)
        self.P = self.P - np.dot(np.dot(K, self.H), self.P)

        self.last_timestamp = timestamp
        return self.x[0], self.x[1]

    def reset(self):
        """Setzt den Filter zurück (z.B. Start eines neuen Mähvorgangs)."""
        self.initialized = False
        self.last_timestamp = None
        self.x = np.array([0.0, 0.0, 0.0, 0.0])
        self.P = np.eye(4) * 1.0
