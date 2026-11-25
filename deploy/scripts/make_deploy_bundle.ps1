# make_deploy_bundle.ps1: Assembles a clean, standalone deployment bundle for Hugging Face Spaces (Windows PowerShell)
[CmdletBinding()]
param (
    [string]$DestinationPath = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = (Resolve-Path "$ScriptDir\..\..").Path

if ([string]::IsNullOrWhiteSpace($DestinationPath)) {
    $DestinationPath = Join-Path $RootDir "deploy\bundle"
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Packaging GPREC Assistant Deployment Bundle" -ForegroundColor Cyan
Write-Host " Source:      $RootDir" -ForegroundColor Gray
Write-Host " Destination: $DestinationPath" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan

# Clean and recreate target folder
if (Test-Path $DestinationPath) {
    Write-Host "Cleaning existing bundle directory..." -ForegroundColor Yellow
    Remove-Item -Path $DestinationPath -Recurse -Force
}
New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null

# 1. Copy core app code and configs
Write-Host "[1/6] Copying app scripts and configs..." -ForegroundColor Green
$coreFiles = @(
    "app.py",
    "config.py",
    "requirements.txt",
    "requirements-dev.txt",
    "Dockerfile",
    ".dockerignore",
    ".gitattributes",
    "README.md",
    "gprec_logo1.png"
)
foreach ($f in $coreFiles) {
    $srcFile = Join-Path $RootDir $f
    if (Test-Path $srcFile) {
        Copy-Item -Path $srcFile -Destination $DestinationPath -Force
    }
}

# 2. Copy source packages and UI
Write-Host "[2/6] Copying src/ and ui/ modules..." -ForegroundColor Green
Copy-Item -Path (Join-Path $RootDir "src") -Destination $DestinationPath -Recurse -Force
if (Test-Path (Join-Path $DestinationPath "src\__pycache__")) {
    Remove-Item -Path (Join-Path $DestinationPath "src\__pycache__") -Recurse -Force
}

Copy-Item -Path (Join-Path $RootDir "ui") -Destination $DestinationPath -Recurse -Force
if (Test-Path (Join-Path $DestinationPath "ui\__pycache__")) {
    Remove-Item -Path (Join-Path $DestinationPath "ui\__pycache__") -Recurse -Force
}

# 3. Copy Streamlit configuration
Write-Host "[3/6] Copying .streamlit/ config..." -ForegroundColor Green
Copy-Item -Path (Join-Path $RootDir ".streamlit") -Destination $DestinationPath -Recurse -Force

# 4. Copy database
Write-Host "[4/6] Copying database (gprec_knowledge.db)..." -ForegroundColor Green
$dbPath = Join-Path $RootDir "gprec_knowledge.db"
if (-not (Test-Path $dbPath)) {
    Write-Error "gprec_knowledge.db not found at $dbPath"
    exit 1
}
Copy-Item -Path $dbPath -Destination $DestinationPath -Force

# 5. Copy vector store
Write-Host "[5/6] Copying vectorstore/ (FAISS index and metadata)..." -ForegroundColor Green
$vsPath = Join-Path $RootDir "vectorstore"
if (-not (Test-Path $vsPath)) {
    Write-Error "vectorstore directory not found at $vsPath"
    exit 1
}
Copy-Item -Path $vsPath -Destination $DestinationPath -Recurse -Force

# 6. Copy faculty photos
Write-Host "[6/6] Copying data/faculty_photos/..." -ForegroundColor Green
$dataPhotos = Join-Path $RootDir "data\faculty_photos"
$destPhotos = Join-Path $DestinationPath "data\faculty_photos"
if (Test-Path $dataPhotos) {
    New-Item -ItemType Directory -Path $destPhotos -Force | Out-Null
    Copy-Item -Path "$dataPhotos\*" -Destination $destPhotos -Recurse -Force
}

# Summary
$fileCount = (Get-ChildItem -Path $DestinationPath -Recurse -File).Count
$totalBytes = (Get-ChildItem -Path $DestinationPath -Recurse -File | Measure-Object -Property Length -Sum).Sum
$totalMB = [math]::Round($totalBytes / 1MB, 2)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Bundle creation completed successfully!" -ForegroundColor Green
Write-Host " Location:    $DestinationPath" -ForegroundColor White
Write-Host " Total files: $fileCount" -ForegroundColor White
Write-Host " Total size:  $totalMB MB" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
