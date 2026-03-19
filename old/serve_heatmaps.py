import http.server
import socketserver
import os
import logging

# --- Konfiguration ---
PORT = 8080  # Port, auf dem der Server laufen soll
DIRECTORY = "."  # Das aktuelle Verzeichnis (wo das Skript liegt)
# --- Ende Konfiguration ---

# Logging einrichten
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class HeatmapRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Initialisiere mit dem angegebenen Verzeichnis
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        # Leite Server-Logs an das logging-Modul weiter
        logging.info(format % args)

    def do_GET(self):
        # Füge Header hinzu, um Caching zu verhindern (optional, aber hilfreich für Aktualisierungen)
        self.send_response(200)
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        # Rufe die ursprüngliche do_GET auf, nachdem die Header gesetzt wurden
        # Wichtig: send_header muss *vor* end_headers() aufgerufen werden,
        # was innerhalb von super().do_GET() passiert. Daher müssen wir es etwas umbauen.

        # Finde den angeforderten Pfad
        fpath = self.translate_path(self.path)
        ctype = self.guess_type(fpath)

        try:
            # Versuche, die Datei zu öffnen
            f = open(fpath, 'rb')
            fs = os.fstat(f.fileno())
            self.send_header("Content-type", ctype)
            self.send_header("Content-Length", str(fs[6]))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            # Sende den Dateiinhalt
            self.copyfile(f, self.wfile)
            f.close()
        except FileNotFoundError:
            self.send_error(404, "File not found")
        except Exception as e:
            logging.error(f"Fehler beim Verarbeiten von GET {self.path}: {e}")
            self.send_error(500, f"Internal server error: {e}")


if __name__ == "__main__":
    # Stelle sicher, dass das Arbeitsverzeichnis korrekt ist (wo das Skript liegt)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    logging.info(f"Arbeitsverzeichnis gesetzt auf: {script_dir}")

    # Erstelle den Server
    try:
        with socketserver.TCPServer(("", PORT), HeatmapRequestHandler) as httpd:
            logging.info(f"Starte HTTP-Server auf Port {PORT}...")
            logging.info(f"Heatmaps sollten erreichbar sein unter:")
            # Versuche, die lokale IP-Adresse zu finden (optional, für Benutzerfreundlichkeit)
            try:
                import socket

                hostname = socket.gethostname()
                ip_address = socket.gethostbyname(hostname)
                logging.info(f"  HTML: http://{ip_address}:{PORT}/heatmaps/heatmap_aktuell.html")
                logging.info(f"  PNG:  http://{ip_address}:{PORT}/heatmaps/heatmap_aktuell.png")
                logging.info(f"  (Ersetze heatmap_aktuell durch den Namen der gewünschten Datei)")
            except Exception:
                logging.warning("Konnte lokale IP-Adresse nicht automatisch ermitteln.")
                logging.info(f"  Versuche http://localhost:{PORT}/heatmaps/...")
                logging.info(f"  Oder http://<IP-DEINES-COMPUTERS>:{PORT}/heatmaps/...")

            logging.info("Drücke Strg+C zum Beenden.")
            # Starte den Server und halte ihn am Laufen
            httpd.serve_forever()
    except OSError as e:
        logging.error(f"Fehler beim Starten des Servers auf Port {PORT}: {e}")
        logging.error("Ist der Port möglicherweise bereits belegt?")
    except KeyboardInterrupt:
        logging.info("\nServer wird beendet.")
    except Exception as e:
        logging.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}")
