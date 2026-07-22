#Requires -Version 5.1
<#
Omni Describe — bootstrap installer (Windows / PowerShell)

Downloaded and piped into `iex` from the omni-media-server install page.
Clones the anagnorisis fork, creates a local venv, installs CUDA torch +
deps, points config at the LAN media server, registers a startup shortcut,
and launches the app.

Nothing here is baked into an image — every run does the real install
steps live on this machine, so there's no giant artifact to build/ship.
#>
$ErrorActionPreference = "Stop"

$RepoUrl      = "https://github.com/arishaig/Anagnorisis.git"
$InstallDir   = "$env:LOCALAPPDATA\omni-describe\app"
$DataDir      = "$env:LOCALAPPDATA\omni-describe\data"
$MediaBaseUrl = "http://192.168.1.110:30817"

function Require-Command($name, $hint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Error "$name is required but not found. $hint"
        exit 1
    }
}

Require-Command git    "Install from https://git-scm.com/download/win and re-run this command."
Require-Command python "Install Python 3.10+ from https://www.python.org/downloads/ and re-run this command."

New-Item -ItemType Directory -Force -Path (Split-Path $InstallDir) | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

if (Test-Path "$InstallDir\.git") {
    Write-Host "Existing install found at $InstallDir — updating..."
    Push-Location $InstallDir
    git pull --ff-only
    Pop-Location
} else {
    Write-Host "Cloning to $InstallDir..."
    git clone --depth 1 $RepoUrl $InstallDir
}

Push-Location $InstallDir

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

$Pip = ".\.venv\Scripts\pip.exe"
& $Pip install --upgrade pip

Write-Host "Installing CUDA-enabled torch (adjust the index URL below if this doesn't match your driver)..."
& $Pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

Write-Host "Installing remaining dependencies..."
& $Pip install -r requirements.txt
& $Pip install requests xxhash

# Point this install's config at the LAN media server and its own local data dir.
$ConfigPath = "$InstallDir\omni_service\config.yaml"
$DataDirForward = $DataDir -replace '\\', '/'
(Get-Content $ConfigPath) `
    -replace 'media_base_url:.*', "media_base_url: `"$MediaBaseUrl`"" `
    -replace 'project_config_directory:.*', "project_config_directory: $DataDirForward" |
    Set-Content $ConfigPath

# Register a startup shortcut so it's running again after every login.
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = "$StartupDir\OmniDescribe.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "$InstallDir\.venv\Scripts\pythonw.exe"
$Shortcut.Arguments = "omni_service\app.py"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.WindowStyle = 7  # minimized
$Shortcut.Save()
Write-Host "Startup shortcut registered: $ShortcutPath"

Write-Host "Starting Omni Describe..."
Start-Process -FilePath "$InstallDir\.venv\Scripts\pythonw.exe" `
    -ArgumentList "omni_service\app.py" -WorkingDirectory $InstallDir -WindowStyle Hidden

Start-Sleep -Seconds 3
Start-Process "http://localhost:5050/"

Pop-Location
Write-Host ""
Write-Host "Done. Omni Describe is running at http://localhost:5050/ and will start automatically on login."
