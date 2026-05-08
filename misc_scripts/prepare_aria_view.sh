#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARIA_CLI="$REPO_ROOT/.venv/bin/aria_gen2"
HELPER="/usr/local/sbin/aria_usb_net_configure"

log() {
  echo "[aria-ready] $*"
}

warn() {
  echo "[aria-ready][warn] $*"
}

if [[ ! -x "$ARIA_CLI" ]]; then
  echo "[aria-ready][error] Missing aria_gen2 CLI at $ARIA_CLI" >&2
  echo "[aria-ready][error] Run: bash misc_scripts/setup_wsl_aria_env.sh" >&2
  exit 1
fi

if [[ ! -x "$HELPER" ]]; then
  echo "[aria-ready][error] Missing helper at $HELPER" >&2
  echo "[aria-ready][error] Run: bash misc_scripts/setup_wsl_aria_env.sh" >&2
  exit 1
fi

matched=0
for iface in /sys/class/net/*; do
  [[ -e "$iface" ]] || continue
  ifname="$(basename "$iface")"

  sys_path="$(readlink -f "$iface/device" 2>/dev/null || true)"
  while [[ -n "$sys_path" && "$sys_path" != "/" ]]; do
    if [[ -f "$sys_path/idVendor" && -f "$sys_path/idProduct" ]]; then
      vendor="$(tr '[:upper:]' '[:lower:]' < "$sys_path/idVendor")"
      product="$(tr '[:upper:]' '[:lower:]' < "$sys_path/idProduct")"
      if [[ "$vendor" == "2833" && "$product" == "9002" ]]; then
        matched=1
        log "Preparing Aria interface: $ifname"
        sudo "$HELPER" "$ifname" || true
        ip -4 -br addr show "$ifname" || true
      fi
      break
    fi
    sys_path="$(dirname "$sys_path")"
  done
done

if [[ "$matched" -eq 0 ]]; then
  warn "No Aria USB network interface found."
  warn "Attach from Windows PowerShell first:"
  warn "usbipd attach --wsl Ubuntu-22.04 --busid <BUSID> --auto-attach"
  exit 2
fi

log "Checking device visibility"
"$ARIA_CLI" device list || true
