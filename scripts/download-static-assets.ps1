# Download required UMD assets into the repository `static/` folder.
# Usage (PowerShell):
#   .\scripts\download-static-assets.ps1
# If you are behind a corporate proxy/firewall, run this when briefly disconnected
# from VPN or use a browser to download the files manually.

$dest = Join-Path -Path $PSScriptRoot -ChildPath "..\static"
$dest = Resolve-Path -Path $dest
if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest | Out-Null }

$files = @{
    'react.development.js' = 'https://unpkg.com/react@18/umd/react.development.js'
    'react-dom.development.js' = 'https://unpkg.com/react-dom@18/umd/react-dom.development.js'
    'babel.min.js' = 'https://unpkg.com/@babel/standalone/babel.min.js'
    'reactflow.min.js' = 'https://unpkg.com/reactflow@11.10.1/dist/umd/reactflow.min.js'
    'reactflow.min.css' = 'https://unpkg.com/reactflow@11.10.1/dist/style.min.css'
}

Write-Host "Downloading UI assets to: $dest" -ForegroundColor Cyan

foreach ($name in $files.Keys) {
    $url = $files[$name]
    $outPath = Join-Path $dest $name
    try {
        Write-Host "- $name from $url" -NoNewline
        Invoke-WebRequest -Uri $url -OutFile $outPath -UseBasicParsing -ErrorAction Stop
        Write-Host " -> saved" -ForegroundColor Green
    } catch {
        Write-Host " -> failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "Done. Verify the files are present in the `static` folder and reload the app." -ForegroundColor Cyan
