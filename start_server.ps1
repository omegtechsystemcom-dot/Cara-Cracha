param(
    [int]$Port = 5000,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonLocal = Join-Path $Root ".venv-local\Scripts\python.exe"
$PythonLegacy = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $PythonLocal) { $PythonLocal } else { $PythonLegacy }
$Url = "http://127.0.0.1:$Port/"
$HealthUrl = "http://127.0.0.1:$Port/api/health"

function Test-Health {
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Stop-ProjectPython {
    $projectPython = (Resolve-Path -LiteralPath $Python -ErrorAction SilentlyContinue)
    if (-not $projectPython) {
        return
    }

    Get-Process -Name python -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $projectPython.Path } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.Id -Force -ErrorAction Stop
            } catch {
                Write-Host "Aviso: nao foi possivel encerrar o processo Python $($_.Id)."
            }
        }
}

function Stop-PortOwner {
    $listeners = netstat -ano |
        Select-String -Pattern "127\.0\.0\.1:$Port\s+.*LISTENING" |
        ForEach-Object {
            $parts = ($_ -split "\s+") | Where-Object { $_ }
            if ($parts.Count -ge 5) { [int]$parts[-1] }
        } |
        Select-Object -Unique

    foreach ($pid in $listeners) {
        try {
            $process = Get-Process -Id $pid -ErrorAction Stop
            if ($process.ProcessName -like "python*") {
                Stop-Process -Id $pid -Force -ErrorAction Stop
            }
        } catch {
            Write-Host "Aviso: nao foi possivel liberar a porta $Port no processo $pid."
        }
    }
}

Set-Location -LiteralPath $Root

if (-not (Test-Path -LiteralPath $Python)) {
    Write-Host "Ambiente virtual nao encontrado. Criando .venv-local..."
    py -3 -m venv .venv-local
    if (-not (Test-Path -LiteralPath $Python)) {
        python -m venv .venv-local
    }
    $Python = $PythonLocal
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Nao foi possivel localizar .venv\Scripts\python.exe."
}

& $Python -c "import flask, pandas, openpyxl, PIL, qrcode" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando dependencias..."
    & $Python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao instalar dependencias."
    }
}

Stop-ProjectPython
Stop-PortOwner

if ($Foreground) {
    Write-Host "Sistema carregado em $Url"
    Start-Process $Url
    & $Python run_server.py
    exit $LASTEXITCODE
}

$serverScript = Join-Path $Root "server_console.ps1"
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-File", "`"$serverScript`"" -WorkingDirectory $Root

$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-Health) {
        $ready = $true
        break
    }
}

if (-not $ready) {
    throw "Servidor nao respondeu em $HealthUrl."
}

Write-Host "Sistema carregado em $Url"
Start-Process $Url
