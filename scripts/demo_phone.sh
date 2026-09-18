#!/bin/zsh
# Bring up the live call backend and a public tunnel, for the phone demo.
#
# The deployed public instance deliberately holds no AWS credentials, so it
# refuses a spoken call by design and says so on screen. This script serves the
# same application from this laptop, which does hold credentials, and exposes it
# on a URL a phone can reach. Type the printed URL into the Connect screen of
# the CALIPER app.
#
# Quick tunnel URLs are ephemeral and the hostname dies with the process, so run
# this again at the venue rather than trusting a URL from a previous session.
set -u
cd "$(dirname "$0")/.."
PORT=8000
LOG="$(mktemp -d)/tunnel.log"

command -v cloudflared > /dev/null || {
  echo "cloudflared is missing. brew install cloudflared"
  exit 1
}

# Refuse to hand out a URL whose backend cannot actually take a call. Credential
# presence is not the check: an expired session still has a credentials object,
# which is how the voice demo died silently once before.
export AWS_PROFILE=caliper
.venv/bin/python -c "
import sys
import boto3
try:
    session = boto3.Session(profile_name='caliper')
    session.get_credentials().get_frozen_credentials()
    session.client('sts', region_name='us-east-1').get_caller_identity()
except Exception as error:
    print('AWS credentials are not usable:', type(error).__name__, error)
    sys.exit(1)
"
if [ $? -ne 0 ]; then
  echo "Fix AWS first. The call will not work."
  exit 1
fi
echo "aws ok"

if ! lsof -ti:$PORT > /dev/null 2>&1; then
  nohup .venv/bin/python -m uvicorn caliper.api.main:app \
    --host 127.0.0.1 --port $PORT --log-level warning > /dev/null 2>&1 &
  for _ in $(seq 1 30); do
    lsof -ti:$PORT > /dev/null 2>&1 && break
    sleep 1
  done
fi
lsof -ti:$PORT > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "backend failed to start on port $PORT"
  exit 1
fi
echo "backend up on port $PORT"

pkill -f "cloudflared tunnel --url" 2> /dev/null
nohup cloudflared tunnel --url "http://127.0.0.1:$PORT" > "$LOG" 2>&1 &
URL=""
for _ in $(seq 1 30); do
  URL=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" "$LOG" 2> /dev/null | head -1)
  [ -n "$URL" ] && break
  sleep 2
done
if [ -z "$URL" ]; then
  echo "tunnel did not come up"
  tail -15 "$LOG"
  exit 1
fi

.venv/bin/python scripts/tunnel_probe.py "$URL"
if [ $? -ne 0 ]; then
  echo "not handing out a URL that cannot take a call"
  exit 1
fi

echo
echo "=================================================="
echo "  Type this into the app Connect screen:"
echo "  $URL"
echo "=================================================="
