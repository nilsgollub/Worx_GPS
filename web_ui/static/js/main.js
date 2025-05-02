// C:/Users/gollu/Documents/GitHub/Worx_GPS/web_ui/static/js/main.js

// --- Socket.IO Setup ---
// Stellt sicher, dass die Socket.IO Client-Bibliothek im HTML eingebunden ist
// <script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script>

const socket = io(); // Verbindet automatisch mit dem Server, von dem die Seite geladen wurde

socket.on('connect', () => {
    console.log('Verbunden mit Server via WebSocket (Socket.IO)');
    // Optional: Visuelles Feedback geben (z.B. Verbindungsstatus-Icon ändern)
    const connectionStatusElement = document.getElementById('mqtt-connection-status');
    if (connectionStatusElement) {
        connectionStatusElement.textContent = 'Verbunden';
        connectionStatusElement.classList.remove('text-danger', 'bg-secondary'); // Entferne alte Klassen
        connectionStatusElement.classList.add('text-success', 'bg-success'); // Füge neue Klassen hinzu
    }
});

socket.on('disconnect', () => {
    console.warn('Verbindung zum Server getrennt');
    // Optional: Visuelles Feedback geben
    const connectionStatusElement = document.getElementById('mqtt-connection-status');
    if (connectionStatusElement) {
        connectionStatusElement.textContent = 'Getrennt';
        connectionStatusElement.classList.remove('text-success', 'bg-success');
        connectionStatusElement.classList.add('text-danger', 'bg-danger');
    }
});

socket.on('connect_error', (err) => {
    console.error('Socket.IO Verbindungsfehler:', err);
    const connectionStatusElement = document.getElementById('mqtt-connection-status');
    if (connectionStatusElement) {
        connectionStatusElement.textContent = 'Fehler';
        connectionStatusElement.classList.remove('text-success', 'bg-success');
        connectionStatusElement.classList.add('text-danger', 'bg-danger');
    }
});


// --- Status-Updates empfangen und anzeigen ---
socket.on('status_update', (data) => {
    console.debug('Status Update empfangen:', data);

    // --- HIER: UI Elemente aktualisieren ---
    // Verwende document.getElementById oder document.querySelector,
    // um die Elemente zu finden und deren Inhalt zu aktualisieren.
    // Stelle sicher, dass die IDs in deinem HTML existieren!

    const statusTextElement = document.getElementById('status-text');
    if (statusTextElement) {
        statusTextElement.innerText = data.status_text || 'N/A';
        // Update badge color based on satellites
        statusTextElement.classList.remove('bg-success', 'bg-warning');
        if (data.satellites >= 4) {
            statusTextElement.classList.add('bg-success');
        } else {
            statusTextElement.classList.add('bg-warning');
        }
    }

    const satellitesElement = document.getElementById('satellites');
    if (satellitesElement) {
        satellitesElement.innerText = data.satellites !== undefined ? data.satellites : 'N/A';
        // Update badge color based on satellites
        satellitesElement.classList.remove('bg-success', 'bg-warning', 'bg-danger');
        if (data.satellites >= 8) {
            satellitesElement.classList.add('bg-success');
        } else if (data.satellites >= 4) {
            satellitesElement.classList.add('bg-warning');
        } else {
            satellitesElement.classList.add('bg-danger');
        }
    }


    const latitudeElement = document.getElementById('latitude');
    if (latitudeElement) latitudeElement.innerText = data.lat !== null ? data.lat.toFixed(6) : 'N/A';

    const longitudeElement = document.getElementById('longitude');
    if (longitudeElement) longitudeElement.innerText = data.lon !== null ? data.lon.toFixed(6) : 'N/A';

    const agpsStatusElement = document.getElementById('agps-status');
    if (agpsStatusElement) agpsStatusElement.innerText = data.agps_status || 'N/A';

    const lastUpdateElement = document.getElementById('last-update');
    if (lastUpdateElement) lastUpdateElement.innerText = data.last_update || 'N/A';

    const recordingStatusElement = document.getElementById('recording-status');
    if (recordingStatusElement) {
        recordingStatusElement.innerText = data.is_recording ? 'Aktiv' : 'Inaktiv'; // Text geändert
        // Klasse ändern für farbliche Markierung
        recordingStatusElement.classList.remove('bg-success', 'bg-danger');
        recordingStatusElement.classList.add(data.is_recording ? 'bg-success' : 'bg-danger');
    }

    // Mäher-Status aktualisieren
    const mowerStatusElement = document.getElementById('mower-status');
    if (mowerStatusElement) mowerStatusElement.innerText = data.mower_status || 'N/A';


    // Wenn eine Live-Karte auf der aktuellen Seite angezeigt wird,
    // rufe die Funktion zum Aktualisieren des Markers auf.
    // Diese Funktion muss im spezifischen Template (z.B. live.html) definiert sein.
    if (typeof updateLiveMarker === 'function' && data.lat !== null && data.lon !== null) {
        updateLiveMarker(data.lat, data.lon);
    }

    // Aktualisiere Button-Status
    const startBtn = document.getElementById('start-rec-button');
    const stopBtn = document.getElementById('stop-rec-button');
    if (startBtn) startBtn.disabled = data.is_recording;
    if (stopBtn) stopBtn.disabled = !data.is_recording;

});

// --- NEU: System-Updates empfangen und anzeigen ---
socket.on('system_update', (data) => {
    console.debug('System Update empfangen:', data);

    const cpuLoadElement = document.getElementById('cpu-load');
    if (cpuLoadElement) cpuLoadElement.innerText = data.cpu_load !== null ? data.cpu_load.toFixed(1) : 'N/A';

    const ramUsageElement = document.getElementById('ram-usage');
    if (ramUsageElement) ramUsageElement.innerText = data.ram_usage !== null ? data.ram_usage.toFixed(1) : 'N/A';

    const cpuTempElement = document.getElementById('cpu-temp');
    if (cpuTempElement) cpuTempElement.innerText = data.cpu_temp !== null ? data.cpu_temp.toFixed(1) : 'N/A';
});
// --- ENDE NEU ---


// --- Steuerbefehle senden ---
function sendControlCommand(command) {
    console.log(`Sende Steuerbefehl: ${command}`);
    // Optional: Zeige Ladeindikator
    const button = document.getElementById(`${command}-button`); // Annahme: Button-ID = command + '-button'
    let originalButtonText = '';
    if (button) {
        originalButtonText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Sende...';
    }

    fetch('/control', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json', // Wichtig: Sende als JSON
        },
        body: JSON.stringify({
            command: command // Sende Objekt mit 'command'-Schlüssel
        })
    })
        .then(response => {
            if (!response.ok) {
                // Wenn der Server einen Fehlerstatus zurückgibt (z.B. 400, 500)
                return response.json().then(errData => {
                    throw new Error(errData.message || `HTTP Fehler ${response.status}`);
                });
            }
            return response.json(); // Bei Erfolg JSON-Antwort parsen
        })
        .then(data => {
            console.log('Antwort vom Server:', data);
            showNotification(data.message || 'Befehl gesendet.', data.success ? 'success' : 'error');
        })
        .catch((error) => {
            console.error('Fehler beim Senden des Steuerbefehls:', error);
            showNotification(`Fehler: ${error.message || 'Unbekannter Fehler beim Senden.'}`, 'error');
        })
        .finally(() => {
            // Optional: Ladeindikator entfernen
            if (button) {
                button.disabled = false; // Re-enable erst nach Antwort (oder Timeout)
                button.innerHTML = originalButtonText;
                // Spezifische Logik für Start/Stop Buttons (wird durch status_update erledigt)
                // if (command === 'start_recording' || command === 'stop_recording') {
                //     // Status wird durch 'status_update' Event aktualisiert
                // } else {
                //     button.disabled = false;
                // }
            }
        });
}

// --- Konfigurationsformular senden ---
function handleConfigFormSubmit(event) {
    event.preventDefault(); // Verhindert das normale Neuladen der Seite
    const form = event.target;
    console.log('Sende Konfigurationsformular...');

    // Erstelle FormData aus dem Formular
    const formData = new FormData(form);

    // --- WICHTIG für Checkboxen ---
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        if (!formData.has(checkbox.name)) {
            formData.append(checkbox.name, 'off'); // 'off' wird vom Backend als False interpretiert
            console.debug(`Checkbox '${checkbox.name}' war nicht gesetzt, sende 'off'.`);
        } else {
            console.debug(`Checkbox '${checkbox.name}' war gesetzt, Wert: '${formData.get(checkbox.name)}'.`);
        }
    });
    // -----------------------------

    // Zeige Ladeindikator
    const saveButton = form.querySelector('button[type="submit"]');
    let originalButtonText = '';
    if (saveButton) {
        originalButtonText = saveButton.innerHTML;
        saveButton.disabled = true;
        saveButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Speichern...';
    }


    fetch('/config/save', {
        method: 'POST',
        body: formData // Sende als FormData
    })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errData => {
                    throw new Error(errData.message || `HTTP Fehler ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Antwort vom Server (Config Save):', data);
            // Zeige Erfolg/Warnung (da Neustart nötig)
            showNotification(data.message || 'Konfiguration gespeichert.', data.success ? 'warning' : 'error');
        })
        .catch(error => {
            console.error('Fehler beim Speichern der Konfiguration:', error);
            showNotification(`Fehler: ${error.message || 'Unbekannter Fehler beim Speichern.'}`, 'error');
        })
        .finally(() => {
            // Ladeindikator entfernen
            if (saveButton) {
                saveButton.disabled = false;
                saveButton.innerHTML = originalButtonText;
            }
        });
}

// --- Hilfsfunktion für Benachrichtigungen (Bootstrap Toasts) ---
function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`); // Log weiterhin

    const toastElement = document.getElementById('notification-toast');
    const toastBody = document.getElementById('toast-message');
    if (!toastElement || !toastBody) {
        console.error("Toast-Elemente nicht im DOM gefunden!");
        alert(`[${type.toUpperCase()}] ${message}`); // Fallback auf alert
        return;
    }

    // Setze Nachricht
    toastBody.textContent = message;

    // Setze Farbe basierend auf Typ
    toastElement.classList.remove('text-bg-success', 'text-bg-warning', 'text-bg-danger', 'text-bg-info'); // Alte Farben entfernen
    switch (type) {
        case 'success':
            toastElement.classList.add('text-bg-success');
            break;
        case 'warning':
            toastElement.classList.add('text-bg-warning');
            break;
        case 'error':
            toastElement.classList.add('text-bg-danger');
            break;
        default:
            toastElement.classList.add('text-bg-info');
            break;
    }

    // Zeige den Toast
    try {
        const toast = bootstrap.Toast.getOrCreateInstance(toastElement);
        toast.show();
    } catch (e) {
        console.error("Fehler beim Anzeigen des Toasts:", e);
        alert(`[${type.toUpperCase()}] ${message}`); // Fallback
    }
}


// --- Event Listener hinzufügen, wenn das DOM geladen ist ---
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM geladen, füge Event Listener hinzu.");

    // Steuer-Buttons (IDs müssen mit HTML übereinstimmen)
    document.getElementById('start-rec-button')?.addEventListener('click', () => sendControlCommand('start_recording'));
    document.getElementById('stop-rec-button')?.addEventListener('click', () => sendControlCommand('stop_recording'));
    document.getElementById('generate-heatmaps-button')?.addEventListener('click', () => sendControlCommand('generate_heatmaps'));

    // Shutdown Button (im Modal) wird in index.html behandelt, da er spezifisch ist

    // Konfigurationsformular
    const configForm = document.getElementById('config-form');
    if (configForm) {
        configForm.addEventListener('submit', handleConfigFormSubmit);
        console.log("Event Listener für Konfigurationsformular hinzugefügt.");
    } else {
        console.debug("Konfigurationsformular nicht auf dieser Seite gefunden.");
    }

});