# BangNotes — local production-mode deploy (PowerShell)
# Usage:
#   .\deploy-local.ps1                  # default: mock LLM (offline), async on
#   $env:DEEPSEEK_API_KEY="sk-..."; .\deploy-local.ps1   # real DeepSeek
# Ports: API 8000, Web 3000.  Logs under %TEMP%\opencode\sn-*.log
param(
  [int]$ApiPort = 8000,
  [int]$WebPort = 3000
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Log  = Join-Path $env:TEMP "opencode"
New-Item -ItemType Directory -Force -Path $Log | Out-Null

function Stop-Port($port) {
  $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($c) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }
}

# 1) stop anything already on our ports
Stop-Port $ApiPort
Stop-Port $WebPort
Start-Sleep -Milliseconds 800

# 2) ensure the frontend production build exists
$buildId = Join-Path $Root "frontend\.next\BUILD_ID"
if (-not (Test-Path $buildId)) {
  Write-Host "Building frontend (first deploy) ..."
  Push-Location (Join-Path $Root "frontend")
  npm run build
  Pop-Location
}

# 3) backend env
$env:ENVIRONMENT = "production-local"
$env:MAIL_DRIVER = if ($env:SMTP_HOST) { "smtp" } else { "console" }
$env:EXEC_ASYNC   = "true"
$env:ADMIN_TOKEN  = if ($env:ADMIN_TOKEN) { $env:ADMIN_TOKEN } else { "dev-admin-secret" }
if ($env:DEEPSEEK_API_KEY) {
  $env:LLM_PROVIDER = "deepseek"
} else {
  $env:LLM_PROVIDER = "mock"
  Write-Host "LLM_PROVIDER=mock (no DEEPSEEK_API_KEY set) - notes will be placeholders."
}
$env:DATABASE_URL = $env:DATABASE_URL  # keep provided or fall back below

$py = Join-Path $Root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "backend venv missing - run: cd backend; python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt" -ForegroundColor Red
  exit 1
}

# 4) start backend (FastAPI, production mode, no reload)
$apiOut = Join-Path $Log "sn-api.out.log"
$apiErr = Join-Path $Log "sn-api.err.log"
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port",$ApiPort -WorkingDirectory (Join-Path $Root "backend") -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr -WindowStyle Hidden | Out-Null

# 5) start frontend (Next.js production server)
$webOut = Join-Path $Log "sn-web.out.log"
$webErr = Join-Path $Log "sn-web.err.log"
if (-not $env:NEXT_PUBLIC_API_BASE) { $env:NEXT_PUBLIC_API_BASE = "http://localhost:$ApiPort/api" }
Start-Process -FilePath "cmd.exe" -ArgumentList "/c","npm run start -- -p $WebPort" -WorkingDirectory (Join-Path $Root "frontend") -RedirectStandardOutput $webOut -RedirectStandardError $webErr -WindowStyle Hidden | Out-Null

# 6) wait + verify
Start-Sleep -Seconds 8
try { $h = Invoke-WebRequest "http://127.0.0.1:$ApiPort/healthz" -UseBasicParsing -TimeoutSec 6; Write-Host "API  : http://localhost:$ApiPort  ($($h.StatusCode))" }
catch { Write-Host "API check failed - see $apiErr" -ForegroundColor Red }
try { $w = Invoke-WebRequest "http://127.0.0.1:$WebPort" -UseBasicParsing -TimeoutSec 8; Write-Host "Web  : http://localhost:$WebPort  ($($w.StatusCode))" }
catch { Write-Host "Web check failed - see $webErr" -ForegroundColor Red }

Write-Host ""
Write-Host "Deployed (local production mode)."
Write-Host "Stop servers with:  .\stop-local.ps1"
Write-Host "Logs: $Log\sn-api.{out,err}.log , sn-web.{out,err}.log"
