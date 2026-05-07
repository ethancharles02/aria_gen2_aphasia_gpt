#!/usr/bin/env bash
# You may need to install WSL Ubuntu before you can run this script. Open Windows Powershell with
# admin privileges and run
#   wsl --install -d Ubuntu-22.04
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
ARIA_SITE_PACKAGES=""

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

  # Activate venv so all subsequent python/pip commands run in the correct environment.
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  log "Installing Python dependencies"
  python -m pip install --upgrade pip
  python -m pip install \
    projectaria-client-sdk==2.3.0 \
    rerun-sdk==0.26.2

  ARIA_SITE_PACKAGES="$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')/aria"
  deactivate
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

  sudo tee /usr/local/sbin/aria_usb_net_configure >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

INTERFACE="$1"

if [[ -z "$INTERFACE" || ! -e "/sys/class/net/$INTERFACE" ]]; then
  exit 0
fi

# Walk up the sysfs path until we find USB idVendor/idProduct and match Aria Gen2.
sys_path="$(readlink -f "/sys/class/net/$INTERFACE/device" 2>/dev/null || true)"
while [[ -n "$sys_path" && "$sys_path" != "/" ]]; do
  if [[ -f "$sys_path/idVendor" && -f "$sys_path/idProduct" ]]; then
    vendor="$(tr '[:upper:]' '[:lower:]' < "$sys_path/idVendor")"
    product="$(tr '[:upper:]' '[:lower:]' < "$sys_path/idProduct")"
    if [[ "$vendor" == "2833" && "$product" == "9002" ]]; then
      /sbin/ip link set dev "$INTERFACE" up || true

      # DHCP can intermittently fail in WSL USBIP; use a bounded retry and fallback.
      if command -v timeout >/dev/null 2>&1; then
        timeout 12s /sbin/dhclient -1 "$INTERFACE" || timeout 12s /usr/sbin/dhclient -1 "$INTERFACE" || true
      else
        /sbin/dhclient -1 "$INTERFACE" || /usr/sbin/dhclient -1 "$INTERFACE" || true
      fi

      # If no IPv4 lease was obtained, set a fallback address on the known Aria USB subnet.
      if ! /sbin/ip -4 addr show dev "$INTERFACE" | grep -q 'inet '; then
        /sbin/ip addr add 192.168.109.64/24 dev "$INTERFACE" 2>/dev/null || true
      fi
    fi
    exit 0
  fi
  sys_path="$(dirname "$sys_path")"
done
EOF
  sudo chmod +x /usr/local/sbin/aria_usb_net_configure

  if [[ -f /etc/NetworkManager/NetworkManager.conf ]]; then
    sudo sed -i 's/managed=false/managed=true/g' /etc/NetworkManager/NetworkManager.conf
  fi

  sudo tee /etc/NetworkManager/dispatcher.d/99-aria-dhcp >/dev/null <<'EOF'
#!/usr/bin/env bash
INTERFACE="$1"
ACTION="$2"

if [[ "$ACTION" == "up" ]]; then
  /usr/local/sbin/aria_usb_net_configure "$INTERFACE"
fi
EOF
  sudo chmod +x /etc/NetworkManager/dispatcher.d/99-aria-dhcp

  sudo tee /etc/udev/rules.d/99-aria-dhcp.rules >/dev/null <<'EOF'
ACTION=="add", SUBSYSTEM=="net", ATTRS{idVendor}=="2833", ATTRS{idProduct}=="9002", RUN+="/usr/local/sbin/aria_usb_net_configure %k"
EOF

  sudo udevadm control --reload-rules || true

  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl restart NetworkManager || warn "Could not restart NetworkManager with systemctl"
  fi

  # If the Aria interface is already attached while setup runs, configure it now.
  for iface in /sys/class/net/*; do
    [[ -e "$iface" ]] || continue
    sudo /usr/local/sbin/aria_usb_net_configure "$(basename "$iface")"
  done
}

ensure_aria_usb_network_ready() {
  log "Ensuring Aria USB network has an IPv4 lease"

  local matched=0
  for iface in /sys/class/net/*; do
    [[ -e "$iface" ]] || continue
    local ifname
    ifname="$(basename "$iface")"

    local sys_path
    sys_path="$(readlink -f "$iface/device" 2>/dev/null || true)"
    while [[ -n "$sys_path" && "$sys_path" != "/" ]]; do
      if [[ -f "$sys_path/idVendor" && -f "$sys_path/idProduct" ]]; then
        local vendor product
        vendor="$(tr '[:upper:]' '[:lower:]' < "$sys_path/idVendor")"
        product="$(tr '[:upper:]' '[:lower:]' < "$sys_path/idProduct")"

        if [[ "$vendor" == "2833" && "$product" == "9002" ]]; then
          matched=1
          sudo /usr/local/sbin/aria_usb_net_configure "$ifname" || true
          local addr
          addr="$(ip -4 -br addr show "$ifname" 2>/dev/null || true)"
          log "Aria USB interface $ifname: $addr"
          if ! echo "$addr" | grep -q 'inet'; then
            warn "No IPv4 lease on $ifname after DHCP — device discovery may fail."
            warn "Try: sudo /usr/local/sbin/aria_usb_net_configure $ifname"
          fi
        fi
        break
      fi
      sys_path="$(dirname "$sys_path")"
    done
  done

  if [[ "$matched" -eq 0 ]]; then
    warn "No Aria USB network interface detected — is the USB attached and usbipd running?"
  fi
}

validate_install() {
  log "Validating Aria imports"
  "$PYTHON_BIN" -c "import aria.sdk_gen2; import aria.stream_receiver; print('Aria SDK import OK')"

  ensure_aria_usb_network_ready
}

print_next_steps() {
  cat <<'EOF'

Setup complete.

Next steps:
1) Install usbipd from Windows Powershell:
    winget install usbipd

2) Check for Aria Glasses in Windows Powershell (look for UsbNcm Host Device):
    usbipd list

3) Attach Aria USB to WSL from Windows PowerShell:
    usbipd attach --wsl Ubuntu-22.04 --busid <BUSID> --auto-attach

4) In WSL, activate venv
    source .venv/bin/activate

5) Run aria_doctor and say yes to any messages it gives
    aria_doctor

6) Run the below script to refresh the USB data to aria can see it:
  ./misc_scripts/prepare_aria_view.sh

7) In WSL, verify device visibility:
    aria_gen2 device list

8) Pair host certificates with the headset (first-time only):
    aria_gen2 auth pair

9) Start device streaming (example profile):
    aria_gen2 streaming start --json-profile agpt_lib/streaming.json --batch-period-ms 200 --interface wifi_sta

10) Start WSL-safe viewer bridge:
    python agpt_lib/wsl_streaming_viewer.py --real-time --interpolate --rerun-memory-limit 4GB

11) In Windows PowerShell, connect Rerun:
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
