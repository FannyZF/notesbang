# Stop the local production servers started by deploy-local.ps1 (ports 8000/3000).
param(
  [int]$ApiPort = 8000,
  [int]$WebPort = 3000
)
function Stop-Port($port) {
  $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if ($c) {
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped process on port $port"
  } else {
    Write-Host "Nothing listening on port $port"
  }
}
Stop-Port $ApiPort
Stop-Port $WebPort
Write-Host "Done."
