#!/bin/sh
# Publish the local CALIPER server on a public HTTPS address.
#
# This is not a convenience. A phone gets NO microphone outside a secure context,
# and a laptop's LAN address over plain HTTP is not one, so a QR code pointing at
# 192.168.x.x yields a judge with a dead button and no error message. A tunnel is
# the shortest path to real TLS, and it also survives client isolation on
# conference wifi, which a LAN address does not.
#
# The hostname is new on every run and the browser binds the microphone grant to
# the exact origin, so PIN THE HOSTNAME BEFORE PRINTING THE QR CODE: a restart
# re prompts every phone that already accepted.
set -e

PORT="${1:-8000}"
LOG="${TMPDIR:-/tmp}/caliper-tunnel.log"

printf 'starting tunnel to http://127.0.0.1:%s\n' "$PORT"
cloudflared tunnel --url "http://127.0.0.1:${PORT}" --no-autoupdate > "$LOG" 2>&1 &
echo $! > "${TMPDIR:-/tmp}/caliper-tunnel.pid"

i=0
while [ $i -lt 40 ]; do
  URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | head -1)
  if [ -n "$URL" ]; then
    printf '\npublic address: %s\n' "$URL"
    printf 'log: %s\n' "$LOG"
    exit 0
  fi
  sleep 1
  i=$((i + 1))
done

echo "the tunnel did not report a hostname; see $LOG"
exit 1
