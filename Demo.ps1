Write-Host "=== Commercial Guardian AI Demo ===" -ForegroundColor Cyan

# Check Infrastructure
$container = docker ps -q -f name=guardian_brain
if (-not $container) {
    Write-Host "Starting AI Infrastructure..." -ForegroundColor Cyan
    docker-compose up -d
    
    Write-Host "Waiting for Neural Engine (First run downloads model)..." -ForegroundColor Yellow
    $ready = $false
    while (-not $ready) {
        try {
            Start-Sleep -Seconds 5
            $ready = $true
        } catch { Write-Host "." -NoNewline }
    }
    Write-Host "Infrastructure Ready." -ForegroundColor Green
}

# Generate Data
if (-not (Test-Path "data/transactions/historical_invoices.csv")) {
    Write-Host "Generating synthetic historical data..." -ForegroundColor Cyan
    docker exec guardian_logic python generate_history.py
}

Write-Host "`nSelect Demo Mode:"
Write-Host "1) Real-time Invoice Audit"
Write-Host "2) Forensic Historical Audit"
$choice = Read-Host "Enter choice [1 or 2]"

if ($choice -eq "1") {
    Write-Host "Running Real-Time Audit..." -ForegroundColor Green
    docker exec -it guardian_logic python guardian_demo.py
} elseif ($choice -eq "2") {
    Write-Host "Running Forensic Analysis..." -ForegroundColor Green
    docker exec -it guardian_logic python guardian_bulk.py
}