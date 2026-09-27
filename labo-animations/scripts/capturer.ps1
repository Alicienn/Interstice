# Captures des pistes à des instants donnés, via Chrome sans interface (WebGL compris).
#   powershell -File scripts/capturer.ps1 -Piste nuee -Instants 3000,9000,14000
param(
  [string]$Piste = "constellation",
  [int[]]$Instants = @(4000, 9500, 17000),
  [string]$Scenario = "outils",
  [string]$Sortie = "$PSScriptRoot\..\captures",
  [string]$Base = "http://localhost:5191"   # `pnpm build && pnpm preview --port 5191` : un seul bundle, chargement immédiat
)
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
New-Item -ItemType Directory -Force $Sortie | Out-Null
foreach ($t in $Instants) {
  $fichier = Join-Path (Resolve-Path $Sortie) "$Piste-$Scenario-$t.png"
  $url = "$Base/?piste=$Piste&scenario=$Scenario&t=$t"
  & $chrome --headless=new --use-angle=swiftshader --enable-unsafe-swiftshader --hide-scrollbars `
    --run-all-compositor-stages-before-draw --window-size=1480,1000 --virtual-time-budget=15000 `
    --screenshot="$fichier" $url 2>$null | Out-Null
  Write-Output $fichier
}
