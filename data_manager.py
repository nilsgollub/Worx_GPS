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
        self.data_folder = Path(data_folder)
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
                        FOREIGN KEY (session_id) REFERENCES mow_sessions(id) ON DELETE CASCADE
                    )
                ''')
                
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
                
                # Indices für Performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_mow_points_session ON mow_points(session_id)')
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Fehler bei der DB-Initialisierung: {e}")

    def save_gps_data(self, data, filename, coverage=0.0):
        """Speichert GPS-Daten in der SQLite DB unter einer Session."""
        if not data:
            return False
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Session anlegen oder updaten
                first_ts = data[0].get('timestamp', datetime.now().timestamp())
                start_dt = datetime.fromtimestamp(first_ts).strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute(
                    "INSERT INTO mow_sessions (filename, start_time, point_count, coverage) VALUES (?, ?, ?, ?)",
                    (filename, start_dt, len(data), coverage)
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
                        p.get('status')
                    )
                    for p in data
                ]
                
                cursor.executemany(
                    "INSERT INTO mow_points (session_id, timestamp, lat, lon, satellites, wifi, speed, heading, battery, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
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
                cursor.execute("DELETE FROM mow_sessions WHERE filename = ?", (filename,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Fehler beim Löschen der Session {filename}: {e}")
            return False
