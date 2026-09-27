#!/usr/bin/env bash
# Install the Cozmo companion on the Linux machine that has the dedicated
# Wi-Fi adapter. Home Assistant itself is added afterwards from the browser.
#
#   curl -fsSL https://raw.githubusercontent.com/fclage/FCL.HA.CozmoAddon/main/install.sh | bash
#
# From a clone you already have:  ./install.sh
# Preview only:                    ./install.sh --dry-run
set -euo pipefail

REPO_URL="https://github.com/fclage/FCL.HA.CozmoAddon.git"
PREFIX="${COZMO_PREFIX:-/opt/ha-cozmo}"
ENV_FILE="${COZMO_ENV_FILE:-/etc/ha-cozmo-companion.env}"
UNIT_NAME="ha-cozmo-companion.service"
DRY=0

if [[ "${1:-}" == "--dry-run" || "${1:-}" == "-n" ]]; then
  DRY=1
fi

say() { printf '%s\n' "$*" >&2; }
die() { say "error: $*"; exit 1; }

run() {
  if [[ "$DRY" == 1 ]]; then
    say "[dry-run] $*"
    return 0
  fi
  "$@"
}

need() {
  command -v "$1" >/dev/null 2>&1 || die "missing '$1'. Install it, then run this again."
}

quote_env() {
  local value=$1
  printf "'%s'" "${value//\'/\'\\\'\'}"
}

prompt() {
  local __var=$1 __text=$2 __secret=${3:-}
  local __current=${!__var:-}
  if [[ -n "$__current" ]]; then
    return 0
  fi
  [[ -r /dev/tty ]] || die "no terminal available to ask for settings. Export $__var and run again."
  local __value
  if [[ "$__secret" == "secret" ]]; then
    read -r -s -p "$__text" __value </dev/tty
    printf '\n' >&2
  else
    read -r -p "$__text" __value </dev/tty
  fi
  printf -v "$__var" '%s' "$__value"
}

confirm() {
  local __text=$1
  [[ -r /dev/tty ]] || return 0
  local __answer
  read -r -p "$__text [Y/n] " __answer </dev/tty
  [[ -z "$__answer" || "$__answer" == [Yy]* ]]
}

need git
need python3
need sudo

if ! python3 -m venv --help >/dev/null 2>&1; then
  die "python3-venv is not installed. On Debian or Ubuntu: sudo apt install python3-venv"
fi

ROOT=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  SOURCE_DIR=$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  if [[ -f "$SOURCE_DIR/companion/requirements.txt" ]]; then
    ROOT=$SOURCE_DIR
  fi
fi

if [[ -z "$ROOT" ]]; then
  say "Cloning into $PREFIX"
  if [[ ! -d "$PREFIX/.git" ]]; then
    run sudo mkdir -p "$(dirname "$PREFIX")"
    run sudo git clone "$REPO_URL" "$PREFIX"
  else
    say "Updating $PREFIX"
    run sudo git -C "$PREFIX" pull --ff-only
  fi
  ROOT=$PREFIX
else
  say "Using the clone at $ROOT"
fi

say "Creating the Python environment in $ROOT/.venv"
run sudo python3 -m venv "$ROOT/.venv"
run sudo "$ROOT/.venv/bin/pip" install --upgrade pip
run sudo "$ROOT/.venv/bin/pip" install -r "$ROOT/companion/requirements.txt"
say "Downloading Cozmo animation assets (faces work without these; clips need them)"
run sudo "$ROOT/.venv/bin/pycozmo_resources.py" download || say "Asset download failed. Faces still work. Re-run pycozmo_resources.py download later."

if command -v nmcli >/dev/null 2>&1; then
  say "Wi-Fi adapters on this machine:"
  nmcli -t -f DEVICE,TYPE,STATE device status | awk -F: '$2=="wifi" { printf "  %s (%s)\n", $1, $3 }' >&2 || true
else
  say "NetworkManager (nmcli) was not found. The companion needs it to join Cozmo."
fi

SSID=${COZMO_SSID:-}
IFACE=${COZMO_WIFI_IFACE:-}
PASSWORD=${COZMO_PASSWORD:-}
ALLOW=${COZMO_ALLOW:-private}

prompt SSID "Cozmo SSID printed on the lift (Cozmo_…): "
prompt IFACE "Wi-Fi adapter dedicated to Cozmo (Enter to let the companion choose): "
prompt PASSWORD "Password printed on the lift: " secret
prompt ALLOW "Who may call the companion [private]: "

[[ -n "$SSID" ]] || die "SSID is required"
[[ -n "$PASSWORD" ]] || die "password is required"
[[ -n "$ALLOW" ]] || ALLOW=private

TMP_ENV=$(mktemp)
chmod 600 "$TMP_ENV"
{
  printf 'COZMO_SSID=%s\n' "$(quote_env "$SSID")"
  printf 'COZMO_PASSWORD=%s\n' "$(quote_env "$PASSWORD")"
  printf 'COZMO_WIFI_IFACE=%s\n' "$(quote_env "$IFACE")"
  printf 'COZMO_HOST=%s\n' '172.31.1.1'
  printf 'COZMO_PORT=%s\n' '5551'
  printf 'LISTEN=%s\n' '0.0.0.0:8790'
  printf 'COZMO_ALLOW=%s\n' "$(quote_env "$ALLOW")"
  printf 'CAMERA_COLOR=%s\n' '1'
  printf 'COZMO_DRY_RUN=%s\n' '0'
} >"$TMP_ENV"
unset PASSWORD

say "Writing $ENV_FILE (root-only, password is not printed)"
run sudo install -m 600 -o root -g root "$TMP_ENV" "$ENV_FILE"
rm -f "$TMP_ENV"

UNIT_TMP=$(mktemp)
cat >"$UNIT_TMP" <<EOF
[Unit]
Description=Cozmo companion
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
# Runs as root so it can join Cozmo's access point with NetworkManager.
User=root
Group=root
WorkingDirectory=$ROOT
EnvironmentFile=$ENV_FILE
ExecStart=$ROOT/.venv/bin/python -m companion
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
run sudo install -m 644 "$UNIT_TMP" "/etc/systemd/system/$UNIT_NAME"
rm -f "$UNIT_TMP"
run sudo systemctl daemon-reload

if [[ "$DRY" == 1 ]]; then
  say "Dry run finished. Nothing was started."
  exit 0
fi

if confirm "Start the companion now?"; then
  sudo systemctl enable --now "$UNIT_NAME"
  sleep 2
  if curl -fsS "http://127.0.0.1:8790/v1/health" >/dev/null; then
    say "Companion is up at http://127.0.0.1:8790"
  else
    say "The service started but health did not answer yet. Check: journalctl -u $UNIT_NAME -e"
  fi
else
  say "Not started. Later: sudo systemctl enable --now $UNIT_NAME"
fi

HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
say ""
say "Next, in Home Assistant:"
say "  1. Use the HACS button in the README to add this repository, download Cozmo, and restart."
say "  2. Use the setup button, or Settings → Devices & services → Add integration → Cozmo."
if [[ -n "${HOST_IP:-}" ]]; then
  say "  3. Companion URL: http://${HOST_IP}:8790"
else
  say "  3. Companion URL: http://<this-machine>:8790"
fi
say "  4. Wi-Fi adapter: ${IFACE:-<leave blank to auto-select>}"
say "  5. SSID: $SSID"
say "The lift password is already in $ENV_FILE. Type it again in Home Assistant; it is not printed here."
