$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$python = Join-Path $root ".venv\Scripts\python.exe"
$distPath = Join-Path $root "backend-dist"
$workPath = Join-Path $root "data\pyinstaller-build"
$specPath = Join-Path $root "data\pyinstaller-spec"
$entryPoint = Join-Path $root "mina_assistant\app\main.py"

if (-not (Test-Path $python)) {
  throw "Python virtual environment not found at $python"
}

if (-not (Test-Path $entryPoint)) {
  throw "Backend entrypoint not found at $entryPoint"
}

New-Item -ItemType Directory -Force -Path $distPath | Out-Null
New-Item -ItemType Directory -Force -Path $workPath | Out-Null
New-Item -ItemType Directory -Force -Path $specPath | Out-Null

& $python -m PyInstaller `
  --onefile `
  --clean `
  --name mina-backend `
  --distpath $distPath `
  --workpath $workPath `
  --specpath $specPath `
  $entryPoint
