#!/bin/zsh
# Re-point the caliper profile at fresh Workshop Studio credentials.
#
# The event account hands out TEMPORARY credentials with a session token, and
# they expire. When they do, the deterministic audit is untouched but the live
# practice call is dead, and the failure surfaces as an ExpiredToken deep in a
# call rather than as anything obvious on screen. So this is a morning-of step,
# not a one-time setup step.
#
# Usage:
#   1. Workshop Studio dashboard, "Get AWS CLI credentials", copy the block.
#   2. ./scripts/refresh_aws.sh
#
# It reads the clipboard, never prints a secret, and refuses to leave a profile
# it could not verify against STS.
set -u

CRED="$HOME/.aws/credentials"
PROFILE="caliper"
REGION="us-east-1"

BLOCK="$(pbpaste 2>/dev/null)"
if [ -z "$BLOCK" ]; then
  echo "Clipboard is empty. Copy the credentials block from Workshop Studio first."
  exit 1
fi

KEY=$(printf '%s\n' "$BLOCK" | sed -nE 's/.*aws_access_key_id[[:space:]]*=[[:space:]]*([A-Za-z0-9/+=]+).*/\1/p' | head -1)
SECRET=$(printf '%s\n' "$BLOCK" | sed -nE 's/.*aws_secret_access_key[[:space:]]*=[[:space:]]*([A-Za-z0-9/+=]+).*/\1/p' | head -1)
TOKEN=$(printf '%s\n' "$BLOCK" | sed -nE 's/.*aws_session_token[[:space:]]*=[[:space:]]*([A-Za-z0-9/+=]+).*/\1/p' | head -1)

# Report only lengths. A credential that reaches a terminal is a credential in
# scrollback, and this one is pasted by hand under time pressure.
echo "parsed from clipboard: key ${#KEY} chars, secret ${#SECRET} chars, token ${#TOKEN} chars"
if [ ${#KEY} -lt 16 ] || [ ${#SECRET} -lt 32 ] || [ ${#TOKEN} -lt 100 ]; then
  echo "That does not look like a Workshop Studio credentials block."
  echo "Expected all three of aws_access_key_id, aws_secret_access_key, aws_session_token."
  exit 1
fi

cp "$CRED" "$CRED.bak-$(date +%Y%m%d-%H%M%S)" 2>/dev/null

python3 - "$CRED" "$PROFILE" "$REGION" "$KEY" "$SECRET" "$TOKEN" <<'PY'
import sys, pathlib
cred_path, profile, region, key, secret, token = sys.argv[1:7]
p = pathlib.Path(cred_path)
lines = p.read_text().splitlines() if p.exists() else []

out, skipping = [], False
for line in lines:
    if line.strip().startswith("["):
        skipping = line.strip() == f"[{profile}]"
        if skipping:
            continue
    if skipping:
        continue
    out.append(line)

while out and not out[-1].strip():
    out.pop()
out += [
    "",
    f"[{profile}]",
    f"aws_access_key_id = {key}",
    f"aws_secret_access_key = {secret}",
    f"aws_session_token = {token}",
    f"region = {region}",
    "",
]
p.write_text("\n".join(out))
p.chmod(0o600)
print(f"wrote the [{profile}] profile")
PY

echo "verifying against STS, because a written profile is not a working one"
AWS_PROFILE="$PROFILE" "$(dirname "$0")/../.venv/bin/python" - <<'PY'
import sys
import boto3
try:
    s = boto3.Session(profile_name="caliper")
    s.get_credentials().get_frozen_credentials()
    who = s.client("sts", region_name="us-east-1").get_caller_identity()
    print(f"  ALIVE, account {who['Account'][:4]}**** role {who['Arn'].split('/')[-1]}")
except Exception as error:
    print(f"  STILL DEAD: {type(error).__name__}: {str(error)[:160]}")
    sys.exit(1)
PY
rc=$?
if [ $rc -ne 0 ]; then
  echo "The profile was written but does not work. Re-copy the block and run this again."
  exit 1
fi
echo
echo "Now bring up the call:  ./scripts/demo_phone.sh"
