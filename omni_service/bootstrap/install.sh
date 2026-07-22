#!/usr/bin/env bash
# Omni Describe — bootstrap installer (WSL / Linux desktop)
#
# Downloaded and piped into `bash` from the omni-media-server install page.
# Clones the anagnorisis fork, creates a local venv, installs CUDA torch +
# deps, points config at the LAN media server, and launches the app.
#
# No auto-start is registered here (unlike the PowerShell version) — WSL
# doesn't have a reliable login hook the way Windows startup folders do.
# Re-run this same command, or just `python omni_service/app.py` from the
# install dir, whenever you want it running again.
set -euo pipefail

REPO_URL="https://github.com/arishaig/Anagnorisis.git"
INSTALL_DIR="${HOME}/.local/share/omni-describe/app"
DATA_DIR="${HOME}/.local/share/omni-describe/data"
MEDIA_BASE_URL="http://192.168.1.110:30817"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1 ($2)"; exit 1; }
}

require git "install via your package manager, e.g. apt install git"
require python3 "install via your package manager, e.g. apt install python3 python3-venv"

mkdir -p "$(dirname "$INSTALL_DIR")" "$DATA_DIR"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Existing install found at $INSTALL_DIR — updating..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "Cloning to $INSTALL_DIR..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

./.venv/bin/pip install --upgrade pip

echo "Installing CUDA-enabled torch (adjust the index URL below if this doesn't match your driver)..."
./.venv/bin/pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

echo "Installing remaining dependencies..."
./.venv/bin/pip install -r requirements.txt
./.venv/bin/pip install requests xxhash

CONFIG_PATH="omni_service/config.yaml"
sed -i \
  -e "s|media_base_url:.*|media_base_url: \"${MEDIA_BASE_URL}\"|" \
  -e "s|project_config_directory:.*|project_config_directory: ${DATA_DIR}|" \
  "$CONFIG_PATH"

echo "Starting Omni Describe..."
nohup ./.venv/bin/python omni_service/app.py > "${DATA_DIR}/omni_service.log" 2>&1 &
disown

sleep 3
if command -v wslview >/dev/null 2>&1; then
  wslview "http://localhost:5050/"
elif command -v cmd.exe >/dev/null 2>&1; then
  cmd.exe /c start http://localhost:5050/ >/dev/null 2>&1 || true
else
  echo "Open http://localhost:5050/ in your browser."
fi

echo ""
echo "Done. Omni Describe is running at http://localhost:5050/ (log: ${DATA_DIR}/omni_service.log)."
echo "Re-run this install command any time you want to start it again."
