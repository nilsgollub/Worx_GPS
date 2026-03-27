# data_manager.py (SQLite-Version)
import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
import os
import glob

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, data_folder="data", db_name="worx_gps.db"):
        # Prüfen ob wir im HA Add-on laufen (überprüfe ob /data existiert)
        ha_data_dir = Path("/data")
        if ha_data_dir.exists() and ha_data_dir.is_dir():
            # Im HA Add-on: nutze persistentes /data Verzeichnis
            self.data_folder = ha_data_dir / "worx_gps"
            logger.info("HA Add-on erkannt, nutze persistentes /data Verzeichnis")
        else:
            # Lokale Entwicklung: nutze angegebenes Verzeichnis
            self.data_folder = Path(data_folder)
            logger.info("Lokale Entwicklung, nutze lokales data Verzeichnis")
        
        self.db_path = self.data_folder / db_name
        
        # Sicherstellen, dass der Ordner existiert
        self.data_folder.mkdir(parents=True, exist_ok=True)
        
        # Datenbank initialisieren
        self._init_db()
        logger.info(f"DataManager mit SQLite initialisiert ({self.db_path})")

    def _init_db(self):
        """Erstellt die Tabellen, falls sie noch nicht existieren."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Tabelle für Mäh-Sessions (Metadaten)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS mow_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT UNIQUE,
                        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        point_count INTEGER DEFAULT 0,
                        coverage REAL DEFAULT 0.0
                    )
                ''')
                
                # Tabelle für GPS-Punkte
                # Wir verwenden die Keys aus utils.py: lat, lon, timestamp, satellites, wifi
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS mow_points (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER,
                        timestamp REAL,
                        lat REAL,
                        lon REAL,
                        satellites INTEGER,
                        wifi INTEGER,
                        speed REAL,
                        heading REAL,
                        battery REAL,
                        status TEXT,
                        hdop REAL,
                        FOREIGN KEY (session_id) REFERENCES mow_sessions(id) ON DELETE CASCADE
                    )
                ''')
                
                # Migration: Prüfen ob hdop Spalte existiert, falls nicht hinzufügen
                cursor.execute("PRAGMA table_info(mow_points)")
                columns = [info[1] for info in cursor.fetchall()]
                if 'hdop' not in columns:
                    logger.info("Migriere Datenbank: Füge 'hdop' Spalte zu 'mow_points' hinzu.")
                    cursor.execute("ALTER TABLE mow_points ADD COLUMN hdop REAL")
                
                # Tabelle für Problemzonen
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS problem_zones (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL,
                        lat REAL,
                        lon REAL,
                        type TEXT,
                        description TEXT
                    )
                ''')
                
                # Tabelle für Geofences (Zäune)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS geofences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        type TEXT,
                        coordinates TEXT, -- JSON-Array von [lat, lon]
                        active INTEGER DEFAULT 1
                    )
                ''')
                
                # Migration: Prüfen ob filter_config Spalte in mow_sessions existiert
                cursor.execute("PRAGMA table_info(mow_sessions)")
                session_columns = [info[1] for info in cursor.fetchall()]
                if 'filter_config' not in session_columns:
                    logger.info("Migriere Datenbank: Füge 'filter_config' Spalte zu 'mow_sessions' hinzu.")
                    cursor.execute("ALTER TABLE mow_sessions ADD COLUMN filter_config TEXT")
                if 'end_time' not in session_columns:
                    logger.info("Migriere Datenbank: Füge 'end_time' Spalte zu 'mow_sessions' hinzu.")
                    cursor.execute("ALTER TABLE mow_sessions ADD COLUMN end_time TIMESTAMP")
                if 'duration_seconds' not in session_columns:
                    logger.info("Migriere Datenbank: Füge 'duration_seconds' Spalte zu 'mow_sessions' hinzu.")
                    cursor.execute("ALTER TABLE mow_sessions ADD COLUMN duration_seconds REAL DEFAULT 0")
                if 'distance_meters' not in session_columns:
                    logger.info("Migriere Datenbank: Füge 'distance_meters' Spalte zu 'mow_sessions' hinzu.")
                    cursor.execute("ALTER TABLE mow_sessions ADD COLUMN distance_meters REAL DEFAULT 0")
                if 'avg_satellites' not in session_columns:
                    logger.info("Migriere Datenbank: Füge 'avg_satellites' Spalte zu 'mow_sessions' hinzu.")
                    cursor.execute("ALTER TABLE mow_sessions ADD COLUMN avg_satellites REAL")
                if 'avg_hdop' not in session_columns:
                    logger.info("Migriere Datenbank: Füge 'avg_hdop' Spalte zu 'mow_sessions' hinzu.")
                    cursor.execute("ALTER TABLE mow_sessions ADD COLUMN avg_hdop REAL")

                # Indices für Performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_mow_points_session ON mow_points(session_id)')
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Fehler bei der DB-Initialisierung: {e}")

    def save_gps_data(self, data, filename, coverage=0.0, filter_config=None):
        """Speichert GPS-Daten in der SQLite DB unter einer Session."""
        if not data:
            return False
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Session anlegen oder updaten
                first_ts = data[0].get('timestamp', datetime.now().timestamp())
                start_dt = datetime.fromtimestamp(first_ts).strftime('%Y-%m-%d %H:%M:%S')
                
                # End-Time und Dauer berechnen
                timestamps = [p.get('timestamp') for p in data if p.get('timestamp') is not None]
                last_ts = max(timestamps) if timestamps else first_ts
                end_dt = datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d %H:%M:%S')
                duration_seconds = last_ts - first_ts if timestamps else 0
                
                # Durchschnittswerte berechnen
                sats = [p.get('satellites') for p in data if p.get('satellites') is not None]
                avg_satellites = sum(sats) / len(sats) if sats else None
                hdops = [p.get('hdop') for p in data if p.get('hdop') is not None]
                avg_hdop = sum(hdops) / len(hdops) if hdops else None
                
                # Distanz berechnen
                distance_meters = 0.0
                for i in range(len(data) - 1):
                    try:
                        lat1, lon1 = float(data[i].get('lat', 0)), float(data[i].get('lon', 0))
                        lat2, lon2 = float(data[i+1].get('lat', 0)), float(data[i+1].get('lon', 0))
                        import math
                        R = 6371000
                        dlat = math.radians(lat2 - lat1)
                        dlon = math.radians(lon2 - lon1)
                        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                        distance_meters += R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                    except (ValueError, TypeError):
                        continue
                
                # Filter-Config als JSON speichern
                filter_config_json = json.dumps(filter_config) if filter_config else None
                
                cursor.execute(
                    """INSERT INTO mow_sessions 
                       (filename, start_time, end_time, point_count, coverage, 
                        duration_seconds, distance_meters, avg_satellites, avg_hdop, filter_config) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (filename, start_dt, end_dt, len(data), coverage,
                     duration_seconds, distance_meters, avg_satellites, avg_hdop, filter_config_json)
                )
                session_id = cursor.lastrowid
                
                # Punkte einfügen. Wir mappen 'wifi' aus dem DB-Schema auf 'wifi' aus utils.py
                points_to_insert = [
                    (
                        session_id,
                        p.get('timestamp'),
                        p.get('lat'),
                        p.get('lon'),
                        p.get('satellites'),
                        p.get('wifi'), # utils.py nutzt 'wifi'
                        p.get('speed'),
                        p.get('heading'),
                        p.get('battery'),
                        p.get('status'),
                        p.get('hdop')
                    )
                    for p in data
                ]
                
                cursor.executemany(
                    "INSERT INTO mow_points (session_id, timestamp, lat, lon, satellites, wifi, speed, heading, battery, status, hdop) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    points_to_insert
                )
                conn.commit()
                logger.info(f"Session {filename} ({len(data)} Punkte) in DB gespeichert.")
                return True
        except Exception as e:
            logger.error(f"Fehler beim Speichern in DB: {e}", exc_info=True)
            return False

    def load_all_mow_data(self):
        """Lädt alle Mähvorgangsdaten (List of Lists of Dicts)."""
        all_data = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT id FROM mow_sessions ORDER BY id ASC")
                session_ids = [row['id'] for row in cursor.fetchall()]
                
                for sid in session_ids:
                    cursor.execute("SELECT * FROM mow_points WHERE session_id = ? ORDER BY timestamp ASC", (sid,))
                    points = [dict(row) for row in cursor.fetchall()]
                    all_data.append(points)
            return all_data
        except Exception as e:
            logger.error(f"Fehler beim Laden aller Mähdaten: {e}")
            return []

    def load_last_mow_data(self, count=1):
        """Lädt die letzten 'count' Mähvorgänge."""
        last_data = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT id FROM mow_sessions ORDER BY start_time DESC LIMIT ?", (count,))
                session_ids = [row['id'] for row in cursor.fetchall()]
                
                for sid in reversed(session_ids): # In chronologischer Reihenfolge zurückgeben
                    cursor.execute("SELECT * FROM mow_points WHERE session_id = ? ORDER BY timestamp ASC", (sid,))
                    points = [dict(row) for row in cursor.fetchall()]
                    last_data.append(points)
            return last_data
        except Exception as e:
            logger.error(f"Fehler beim Laden der letzten Mähdaten: {e}")
            return []

    def get_all_mow_session_details(self):
        """Gibt Details zu allen Sessions zurück (für die UI)."""
        session_details = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM mow_sessions ORDER BY start_time DESC")
                for session in cursor.fetchall():
                    sid = session['id']
                    filename = session['filename']
                    
                    cursor.execute("SELECT * FROM mow_points WHERE session_id = ? ORDER BY timestamp ASC", (sid,))
                    data = [dict(row) for row in cursor.fetchall()]
                    
                    session_details.append({
                        "filename": filename,
                        "first_timestamp": data[0].get('timestamp') if data else None,
                        "point_count": session['point_count'],
                        "coverage": session['coverage'],
                        "data": data
                    })
            return session_details
        except Exception as e:
            logger.error(f"Fehler bei get_all_mow_session_details: {e}")
            return []

    def add_problemzone(self, problem_data):
        """Speichert eine neue Problemzone."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO problem_zones (timestamp, lat, lon, type) VALUES (?,?,?,?)",
                    (problem_data.get('timestamp'), problem_data.get('lat'), problem_data.get('lon'), problem_data.get('type'))
                )
                conn.commit()
                # Bereinigung alter Zonen (älter als 60 Tage)
                two_months_ago = (datetime.now() - timedelta(days=60)).timestamp()
                cursor.execute("DELETE FROM problem_zones WHERE timestamp < ?", (two_months_ago,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen einer Problemzone: {e}")
            return False

    def read_problemzonen_data(self):
        """Gibt Problemzonen zurück."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM problem_zones ORDER BY timestamp ASC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Fehler beim Lesen der Problemzonen: {e}")
            return []

    def get_next_mow_filename(self):
        """Simuliert Dateinamen basierend auf DB IDs für Kompatibilität."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(id) FROM mow_sessions")
                res = cursor.fetchone()[0]
                next_num = (res or 0) + 1
                return f"maehvorgang_{next_num}.json"
        except:
            return "maehvorgang_1.json"

    def delete_mow_session_file(self, filename: str) -> bool:
        """Löscht eine Session aus der DB."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM mow_points WHERE session_id IN (SELECT id FROM mow_sessions WHERE filename = ?)", (filename,))
                cursor.execute("DELETE FROM mow_sessions WHERE filename = ?", (filename,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Fehler beim Löschen der Session {filename}: {e}")
            return False

    def reset_database(self, include_geofences=False):
        """Setzt die gesamte Datenbank zurück (löscht alle Mähsessions)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Mähsessions und deren Punkte löschen
                cursor.execute("DELETE FROM mow_points")
                cursor.execute("DELETE FROM mow_sessions")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'mow_sessions'")
                
                # Optional auch Geofences löschen
                if include_geofences:
                    cursor.execute("DELETE FROM geofences")
                    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'geofences'")
                    logger.info("Datenbank zurückgesetzt: Sessions und Geofences gelöscht.")
                else:
                    logger.info("Datenbank zurückgesetzt: Nur Mähsessions gelöscht (Geofences erhalten).")
                
                conn.commit()
        except Exception as e:
            logger.error(f"Fehler beim Zurücksetzen der Datenbank: {e}")
            raise
    # Geofencing Methoden
    def get_geofences(self):
        """Lädt alle Geofences aus der Datenbank."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM geofences")
                rows = cursor.fetchall()
                
                geofences = []
                for row in rows:
                    geo = dict(row)
                    try:
                        geo['coordinates'] = json.loads(geo['coordinates'])
                    except:
                        geo['coordinates'] = []
                    geofences.append(geo)
                return geofences
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Laden der Geofences: {e}")
            return []

    def save_geofence(self, name, type, coordinates, fence_id=None):
        """Speichert einen neuen oder aktualisiert einen bestehenden Geofence."""
        try:
            coords_json = json.dumps(coordinates)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if fence_id:
                    cursor.execute(
                        "UPDATE geofences SET name = ?, type = ?, coordinates = ? WHERE id = ?",
                        (name, type, coords_json, fence_id)
                    )
                    conn.commit()
                    return fence_id
                else:
                    cursor.execute(
                        "INSERT INTO geofences (name, type, coordinates) VALUES (?, ?, ?)",
                        (name, type, coords_json)
                    )
                    conn.commit()
                    return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Speichern des Geofence: {e}")
            return None

    def delete_geofence(self, geofence_id):
        """Löscht einen Geofence anhand der ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM geofences WHERE id = ?", (geofence_id,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Löschen des Geofence: {e}")
            return False

    # --- Datenbank-Manager Methoden ---

    def get_session_by_id(self, session_id):
        """Gibt eine einzelne Session mit allen Metadaten zurück."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM mow_sessions WHERE id = ?", (session_id,))
                row = cursor.fetchone()
                if row:
                    session = dict(row)
                    if session.get('filter_config'):
                        try:
                            session['filter_config'] = json.loads(session['filter_config'])
                        except json.JSONDecodeError:
                            pass
                    return session
                return None
        except sqlite3.Error as e:
            logger.error(f"Fehler bei get_session_by_id: {e}")
            return None

    def get_session_points(self, session_id):
        """Gibt alle GPS-Punkte einer Session zurück."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM mow_points WHERE session_id = ? ORDER BY timestamp ASC",
                    (session_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"Fehler bei get_session_points: {e}")
            return []

    def get_all_sessions_summary(self):
        """Gibt eine kompakte Übersicht aller Sessions zurück (ohne Punkte)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT s.*, 
                           (SELECT COUNT(*) FROM mow_points WHERE session_id = s.id) as actual_point_count,
                           (SELECT MIN(timestamp) FROM mow_points WHERE session_id = s.id) as first_ts,
                           (SELECT MAX(timestamp) FROM mow_points WHERE session_id = s.id) as last_ts,
                           (SELECT AVG(satellites) FROM mow_points WHERE session_id = s.id) as calc_avg_sats,
                           (SELECT AVG(hdop) FROM mow_points WHERE session_id = s.id) as calc_avg_hdop,
                           (SELECT MIN(hdop) FROM mow_points WHERE session_id = s.id) as min_hdop,
                           (SELECT MAX(hdop) FROM mow_points WHERE session_id = s.id) as max_hdop
                    FROM mow_sessions s
                    ORDER BY s.start_time DESC
                """)
                sessions = []
                for row in cursor.fetchall():
                    session = dict(row)
                    if session.get('filter_config'):
                        try:
                            session['filter_config'] = json.loads(session['filter_config'])
                        except json.JSONDecodeError:
                            pass
                    # Fallback für alte Sessions ohne berechnete Werte
                    if session.get('avg_satellites') is None:
                        session['avg_satellites'] = session.get('calc_avg_sats')
                    if session.get('avg_hdop') is None:
                        session['avg_hdop'] = session.get('calc_avg_hdop')
                    sessions.append(session)
                return sessions
        except sqlite3.Error as e:
            logger.error(f"Fehler bei get_all_sessions_summary: {e}")
            return []

    def delete_session_by_id(self, session_id):
        """Löscht eine Session und deren Punkte anhand der ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM mow_points WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM mow_sessions WHERE id = ?", (session_id,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Löschen der Session {session_id}: {e}")
            return False

    def get_database_info(self):
        """Gibt allgemeine Datenbank-Informationen zurück."""
        try:
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM mow_sessions")
                session_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM mow_points")
                point_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM geofences")
                geofence_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM problem_zones")
                problem_count = cursor.fetchone()[0]
                
                return {
                    'db_path': str(self.db_path),
                    'db_size_bytes': db_size,
                    'db_size_mb': round(db_size / (1024 * 1024), 2),
                    'session_count': session_count,
                    'point_count': point_count,
                    'geofence_count': geofence_count,
                    'problem_zone_count': problem_count,
                    'tables': ['mow_sessions', 'mow_points', 'geofences', 'problem_zones']
                }
        except sqlite3.Error as e:
            logger.error(f"Fehler bei get_database_info: {e}")
            return {'error': str(e)}

    def get_session_quality_stats(self):
        """Gibt Qualitätsstatistiken pro Session für Langzeitanalyse zurück."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        s.id,
                        s.start_time,
                        s.point_count,
                        s.coverage,
                        s.duration_seconds,
                        s.distance_meters,
                        s.filter_config,
                        AVG(p.satellites) as avg_satellites,
                        MIN(p.satellites) as min_satellites,
                        MAX(p.satellites) as max_satellites,
                        AVG(p.hdop) as avg_hdop,
                        MIN(p.hdop) as min_hdop,
                        MAX(p.hdop) as max_hdop,
                        AVG(p.wifi) as avg_wifi
                    FROM mow_sessions s
                    LEFT JOIN mow_points p ON p.session_id = s.id
                    GROUP BY s.id
                    ORDER BY s.start_time ASC
                """)
                stats = []
                for row in cursor.fetchall():
                    entry = dict(row)
                    if entry.get('filter_config'):
                        try:
                            entry['filter_config'] = json.loads(entry['filter_config'])
                        except json.JSONDecodeError:
                            pass
                    stats.append(entry)
                return stats
        except sqlite3.Error as e:
            logger.error(f"Fehler bei get_session_quality_stats: {e}")
            return []
