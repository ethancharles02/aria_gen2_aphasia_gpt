#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
ARIA_SITE_PACKAGES="$VENV_DIR/lib/python3.10/site-packages/aria"

log() {
  echo "[setup] $*"
}

warn() {
  echo "[setup][warn] $*"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[setup][error] Missing required command: $1" >&2
    exit 1
  }
}

ensure_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    return
  fi
  sudo -v
}

install_apt_prereqs() {
  log "Installing apt prerequisites"
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    software-properties-common \
    python3 \
    python3-venv \
    python3-pip \
    libatomic1 \
    network-manager \
    usbutils
}

ensure_new_libstdcpp() {
  if strings /lib/x86_64-linux-gnu/libstdc++.so.6 | grep -q "GLIBCXX_3.4.32"; then
    log "libstdc++ already provides GLIBCXX_3.4.32"
    return
  fi

  log "Upgrading libstdc++ from ubuntu-toolchain-r/test PPA"
  sudo add-apt-repository -y ppa:ubuntu-toolchain-r/test
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y libstdc++6
}

setup_python_env() {
  if [[ ! -d "$VENV_DIR" ]]; then
    log "Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  else
    log "Using existing virtual environment at $VENV_DIR"
  fi

  log "Installing Python dependencies"
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PIP_BIN" install \
    projectaria-client-sdk==2.3.0 \
    rerun-sdk==0.26.2
}

fix_sdk_shared_object_suffixes() {
  if [[ ! -d "$ARIA_SITE_PACKAGES" ]]; then
    warn "Aria site-packages not found at $ARIA_SITE_PACKAGES; skipping ABI symlink fix"
    return
  fi

  local sdk_gen2_fb="$ARIA_SITE_PACKAGES/sdk_gen2.cpython-310-fb-010-x86_64.so"
  local sdk_fb="$ARIA_SITE_PACKAGES/sdk.cpython-310-fb-010-x86_64.so"

  if [[ -f "$sdk_gen2_fb" ]]; then
    ln -sf "$(basename "$sdk_gen2_fb")" "$ARIA_SITE_PACKAGES/sdk_gen2.cpython-310-x86_64-linux-gnu.so"
    log "Ensured sdk_gen2 ABI compatibility symlink"
  fi

  if [[ -f "$sdk_fb" ]]; then
    ln -sf "$(basename "$sdk_fb")" "$ARIA_SITE_PACKAGES/sdk.cpython-310-x86_64-linux-gnu.so"
    log "Ensured sdk ABI compatibility symlink"
  fi
}

configure_network_manager_for_aria() {
  log "Configuring NetworkManager and udev for Aria USB interface"

  if [[ -f /etc/NetworkManager/NetworkManager.conf ]]; then
    sudo sed -i 's/managed=false/managed=true/g' /etc/NetworkManager/NetworkManager.conf
  fi

  sudo tee /etc/NetworkManager/dispatcher.d/99-aria-dhcp >/dev/null <<'EOF'
#!/usr/bin/env bash
INTERFACE="$1"
ACTION="$2"

if [[ "$INTERFACE" == "aria_gen2" && "$ACTION" == "up" ]]; then
  dhclient aria_gen2 || true
fi
EOF
  sudo chmod +x /etc/NetworkManager/dispatcher.d/99-aria-dhcp

  sudo tee /etc/udev/rules.d/99-aria-dhcp.rules >/dev/null <<'EOF'
ACTION=="add", SUBSYSTEM=="net", ATTRS{idVendor}=="2833", ATTRS{idProduct}=="9002", RUN+="/sbin/dhclient aria_gen2"
EOF

  sudo udevadm control --reload-rules || true

  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl restart NetworkManager || warn "Could not restart NetworkManager with systemctl"
  fi
}

validate_install() {
  log "Validating Aria imports"
  "$PYTHON_BIN" -c "import aria.sdk_gen2; import aria.stream_receiver; print('Aria SDK import OK')"
}

print_next_steps() {
  cat <<'EOF'

Setup complete.

Next steps:
1) Attach Aria USB to WSL from Windows PowerShell:
   usbipd attach --wsl --busid <BUSID>

2) In WSL, verify device visibility:
   .venv/bin/aria_gen2 device list

3) Start device streaming (example profile):
   .venv/bin/aria_gen2 streaming start --json-profile agpt_lib/streaming.json --batch-period-ms 200 --interface wifi_sta

4) Start WSL-safe viewer bridge:
   .venv/bin/python agpt_lib/wsl_streaming_viewer.py --real-time --interpolate --rerun-memory-limit 4GB

5) In Windows PowerShell, connect Rerun:
   py -m rerun rerun+http://127.0.0.1:9876/proxy
EOF
}

main() {
  need_cmd python3
  need_cmd sudo
  ensure_sudo

  install_apt_prereqs
  ensure_new_libstdcpp
  setup_python_env
  fix_sdk_shared_object_suffixes
  configure_network_manager_for_aria
  validate_install
  print_next_steps
}

main "$@"
