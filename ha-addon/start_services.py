# start_services.py
import subprocess
import sys
import threading
import os
import time
from datetime import datetime

# ANSI Color Codes für eine übersichtliche Konsole
class Colors:
    LOGIC = '\033[94m'  # Blau
    WEBUI = '\033[92m'  # Grün
    SYSTEM = '\033[95m' # Magenta
    INFO = '\033[96m'   # Cyan
    WARN = '\033[93m'   # Gelb
    ERR = '\033[91m'    # Rot
    BOLD = '\033[1m'
    END = '\033[0m'

def colorize_content(line):
    """Hebt wichtige Begriffe innerhalb einer Zeile hervor."""
    l_upper = line.upper()
    if any(k in l_upper for k in ["ERROR", "EXCEPTION", "FEHLER", "CRITICAL"]):
        return f"{Colors.ERR}{line}{Colors.END}"
    if any(k in l_upper for k in ["WARN", "WARNING", "WARNUNG"]):
        return f"{Colors.WARN}{line}{Colors.END}"
    if any(k in l_upper for k in ["MAP", "KARTE", "HEATMAP", "GENERIEREN", "AKTUALISIERUNG", "SAVING"]):
        return f"{Colors.INFO}{Colors.BOLD}{line}{Colors.END}"
    if any(k in l_upper for k in ["START", "GESTARTET", "INITIALISIERT", "SUCCESS", "ERFOLGREICH"]):
        return f"{Colors.INFO}{line}{Colors.END}"
    return line

def format_line(line, name):
    """Formatierte Zeile mit Zeitstempel und farbigem Präfix."""
    ts = datetime.now().strftime("%H:%M:%S")
    color = Colors.LOGIC if name == "LOGIC" else Colors.WEBUI
    if name == "SYSTEM": color = Colors.SYSTEM
    content = colorize_content(line)
    return f"{Colors.SYSTEM}[{ts}] {color}{name:6}{Colors.END} | {content}"

def stream_output(process, name):
    """Liest den Output eines Prozesses und gibt ihn formatiert aus."""
    for line in iter(process.stdout.readline, ""):
        if line:
            print(format_line(line.strip(), name))
    process.stdout.close()

def start_services():
    # ANSI Farben unter Windows aktivieren
    if os.name == 'nt':
        os.system('color')

    root_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = sys.executable
    
    # Pfade zu den Skripten
    logic_script = os.path.join(root_dir, "Worx_GPS.py")
    webui_script = os.path.join(root_dir, "web_ui", "webui.py")
    
    processes = []
    
    # Umgebungsvariablen für sofortiges Logging (kein Buffering)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    print(f"\n{Colors.SYSTEM}{Colors.BOLD}{'='*65}{Colors.END}")
    print(f"{Colors.SYSTEM}{Colors.BOLD}   Worx GPS Monitoring - System Start{Colors.END}")
    print(f"{Colors.SYSTEM}{Colors.BOLD}{'='*65}{Colors.END}\n")

    # 1. Worx_GPS.py starten
    print(format_line("Starte LOGIC Dienst...", "SYSTEM"))
    p_logic = subprocess.Popen(
        [python_exe, logic_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=root_dir,
        env=env
    )
    processes.append(p_logic)
    threading.Thread(target=stream_output, args=(p_logic, "LOGIC"), daemon=True).start()

    time.sleep(1.5)

    # 2. webui.py starten
    print(format_line("Starte WEBUI Dashboard...", "SYSTEM"))
    p_web = subprocess.Popen(
        [python_exe, webui_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=os.path.join(root_dir, "web_ui"),
        env=env
    )
    processes.append(p_web)
    threading.Thread(target=stream_output, args=(p_web, "WEBUI"), daemon=True).start()

    print(f"\n{Colors.SYSTEM}[!] System bereit. Beenden mit Strg+C.{Colors.END}\n")

    try:
        while True:
            if p_logic.poll() is not None:
                print(format_line("LOGIC wurde unerwartet beendet!", "SYSTEM"))
                break
            if p_web.poll() is not None:
                print(format_line("WEBUI wurde unerwartet beendet!", "SYSTEM"))
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{Colors.SYSTEM}[!] Beenden-Signal empfangen...{Colors.END}")
    finally:
        for p in processes:
            p.terminate()
            try:
                p.wait(timeout=2)
            except:
                p.kill()
        print(f"{Colors.SYSTEM}[✓] Alle Dienste gestoppt.{Colors.END}")

if __name__ == "__main__":
    start_services()
