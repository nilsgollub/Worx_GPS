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


// --- Status-Updates empfangen und anzeigen (GPS/Mäher) ---
socket.on('status_update', (data) => {
    // ... (Code wie vorher) ...
    console.debug('Status Update empfangen:', data);
    const statusTextElement = document.getElementById('status-text');
    if (statusTextElement) { /* ... */
    }
    const satellitesElement = document.getElementById('satellites');
    if (satellitesElement) { /* ... */
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
    if (recordingStatusElement) { /* ... */
    }
    const mowerStatusElement = document.getElementById('mower-status');
    if (mowerStatusElement) mowerStatusElement.innerText = data.mower_status || 'N/A';

    if (typeof updateLiveMarker === 'function' && data.lat !== null && data.lon !== null) {
        updateLiveMarker(data.lat, data.lon);
    }
    const startBtn = document.getElementById('start-rec-button');
    const stopBtn = document.getElementById('stop-rec-button');
    if (startBtn) startBtn.disabled = data.is_recording;
    if (stopBtn) stopBtn.disabled = !data.is_recording;
});

// --- System-Updates empfangen und anzeigen (Webserver) ---
socket.on('system_update', (data) => {
    // ... (Code wie vorher) ...
    console.debug('System Update empfangen:', data);
    const cpuLoadElement = document.getElementById('cpu-load');
    if (cpuLoadElement) cpuLoadElement.innerText = data.cpu_load !== null ? data.cpu_load.toFixed(1) : 'N/A';
    const ramUsageElement = document.getElementById('ram-usage');
    if (ramUsageElement) ramUsageElement.innerText = data.ram_usage !== null ? data.ram_usage.toFixed(1) : 'N/A';
    const cpuTempElement = document.getElementById('cpu-temp');
    if (cpuTempElement) cpuTempElement.innerText = data.cpu_temp !== null ? data.cpu_temp.toFixed(1) : 'N/A';
});

// --- NEU: Pi-Status Updates empfangen und anzeigen ---
socket.on('pi_status_update', (data) => {
    console.debug('Pi Status Update empfangen:', data);

    const piTempElement = document.getElementById('pi-temp');
    if (piTempElement) {
        piTempElement.innerText = data.temperature !== null ? data.temperature.toFixed(1) : 'N/A';
    }

    const piLastUpdateElement = document.getElementById('pi-last-update');
    if (piLastUpdateElement) {
        piLastUpdateElement.innerText = data.last_update || 'N/A';
    }
});
// --- ENDE NEU ---

// --- Steuerbefehle senden (unverändert) ---
function sendControlCommand(command) {
    // ... (Code wie vorher) ...
    console.log(`Sende Steuerbefehl: ${command}`);
    const button = document.getElementById(`${command}-button`);
    let originalButtonText = '';
    if (button) {
        originalButtonText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Sende...';
    }
    fetch('/control', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({command: command})
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
            console.log('Antwort vom Server:', data);
            showNotification(data.message || 'Befehl gesendet.', data.success ? 'success' : 'error');
        })
        .catch((error) => {
            console.error('Fehler beim Senden des Steuerbefehls:', error);
            showNotification(`Fehler: ${error.message || 'Unbekannter Fehler beim Senden.'}`, 'error');
        })
        .finally(() => {
            if (button) {
                button.disabled = false;
                button.innerHTML = originalButtonText;
            }
        });
}

// --- Konfigurationsformular senden (unverändert) ---
function handleConfigFormSubmit(event) {
    // ... (Code wie vorher) ...
    event.preventDefault();
    const form = event.target;
    console.log('Sende Konfigurationsformular...');
    const formData = new FormData(form);
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        if (!formData.has(checkbox.name)) {
            formData.append(checkbox.name, 'off');
            console.debug(`Checkbox '${checkbox.name}' war nicht gesetzt, sende 'off'.`);
        } else {
            console.debug(`Checkbox '${checkbox.name}' war gesetzt, Wert: '${formData.get(checkbox.name)}'.`);
        }
    });
    const saveButton = form.querySelector('button[type="submit"]');
    let originalButtonText = '';
    if (saveButton) {
        originalButtonText = saveButton.innerHTML;
        saveButton.disabled = true;
        saveButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Speichern...';
    }
    fetch('/config/save', {
        method: 'POST',
        body: formData
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
            showNotification(data.message || 'Konfiguration gespeichert.', data.success ? 'warning' : 'error');
        })
        .catch(error => {
            console.error('Fehler beim Speichern der Konfiguration:', error);
            showNotification(`Fehler: ${error.message || 'Unbekannter Fehler beim Speichern.'}`, 'error');
        })
        .finally(() => {
            if (saveButton) {
                saveButton.disabled = false;
                saveButton.innerHTML = originalButtonText;
            }
        });
}

// --- Hilfsfunktion für Benachrichtigungen (unverändert) ---
function showNotification(message, type = 'info') {
    // ... (Code wie vorher) ...
    console.log(`[${type.toUpperCase()}] ${message}`);
    const toastElement = document.getElementById('notification-toast');
    const toastBody = document.getElementById('toast-message');
    if (!toastElement || !toastBody) {
        console.error("Toast-Elemente nicht im DOM gefunden!");
        alert(`[${type.toUpperCase()}] ${message}`);
        return;
    }
    toastBody.textContent = message;
    toastElement.classList.remove('text-bg-success', 'text-bg-warning', 'text-bg-danger', 'text-bg-info');
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
    try {
        const toast = bootstrap.Toast.getOrCreateInstance(toastElement);
        toast.show();
    } catch (e) {
        console.error("Fehler beim Anzeigen des Toasts:", e);
        alert(`[${type.toUpperCase()}] ${message}`);
    }
}


// --- Event Listener hinzufügen (unverändert) ---
document.addEventListener('DOMContentLoaded', () => {
    // ... (Code wie vorher) ...
    console.log("DOM geladen, füge Event Listener hinzu.");
    document.getElementById('start-rec-button')?.addEventListener('click', () => sendControlCommand('start_recording'));
    document.getElementById('stop-rec-button')?.addEventListener('click', () => sendControlCommand('stop_recording'));
    document.getElementById('generate-heatmaps-button')?.addEventListener('click', () => sendControlCommand('generate_heatmaps'));
    const configForm = document.getElementById('config-form');
    if (configForm) {
        configForm.addEventListener('submit', handleConfigFormSubmit);
        console.log("Event Listener für Konfigurationsformular hinzugefügt.");
    } else {
        console.debug("Konfigurationsformular nicht auf dieser Seite gefunden.");
    }
});