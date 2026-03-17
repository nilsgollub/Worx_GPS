# PowerShell Script zum Upload auf RPi (Windows)
# Führe aus: powershell -ExecutionPolicy Bypass -File upload_to_pi.ps1

$RaspiHost = "192.168.1.202"
$RaspiUser = "nilsgollub"
$RaspiPath = "Worx_GPS"

Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Upload Scripts zum Raspberry Pi       ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Prüfe ob sshpass oder ssh funktioniert
Write-Host "1️⃣  Prüfe SSH-Verbindung..." -ForegroundColor Yellow

$testCmd = ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no $RaspiUser@$RaspiHost "echo test" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ SSH-Verbindung OK" -ForegroundColor Green
} else {
    # Versuche mit sshpass (falls installiert)
    Write-Host "⚠️  SSH-Verbindung failed, versuche alternatives Verfahren..." -ForegroundColor Yellow
}

# Upload via SSH + here-doc
Write-Host ""
Write-Host "2️⃣  Uploade run_funktionscheck.sh..." -ForegroundColor Yellow

# Lese lokale Datei
$funktionsCheckContent = Get-Content -Path "run_funktionscheck.sh" -Raw
$escapedContent = $funktionsCheckContent -replace '"', '\"' -replace '$', '`$'

# Schreibe auf Pi via SSH
ssh -o StrictHostKeyChecking=no $RaspiUser@$RaspiHost @"
cat > ~/Worx_GPS/run_funktionscheck.sh << 'EOF'
$(Get-Content -Path "run_funktionscheck.sh" -Raw)
EOF
chmod +x ~/Worx_GPS/run_funktionscheck.sh
"@ 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ run_funktionscheck.sh uploaded" -ForegroundColor Green
} else {
    Write-Host "❌ Upload failed" -ForegroundColor Red
}

# Upload check_raspi.sh
Write-Host ""
Write-Host "3️⃣  Uploade check_raspi.sh..." -ForegroundColor Yellow

ssh -o StrictHostKeyChecking=no $RaspiUser@$RaspiHost @"
cat > ~/Worx_GPS/check_raspi.sh << 'EOF'
$(Get-Content -Path "check_raspi.sh" -Raw)
EOF
chmod +x ~/Worx_GPS/check_raspi.sh
"@ 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ check_raspi.sh uploaded" -ForegroundColor Green
} else {
    Write-Host "❌ Upload failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Script Upload Abgeschlossen          ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan

Write-Host ""
Write-Host "Nächste Schritte:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. SSH zum Pi:" -ForegroundColor Yellow
Write-Host "   ssh $RaspiUser@$RaspiHost" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Funktionscheck durchführen:" -ForegroundColor Yellow
Write-Host "   cd ~/Worx_GPS && bash run_funktionscheck.sh" -ForegroundColor Gray
Write-Host ""
