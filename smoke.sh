#!/bin/bash
# smoke.sh <image>: runs the image against a real headless Chrome on this host (host network) and checks
# tool list, uid, no shell, telemetry env, page isolation between sessions (smoke/isolation.py) and
# reconnect after a browser restart. Needs docker, python3 and Chrome ($CHROME_BIN, default google-chrome).
set -euo pipefail
IMG="$1"; NAME="browser-mcp-smoke-$$"
HERE="$(cd "$(dirname "$0")" && pwd)"
CHROME_BIN="${CHROME_BIN:-google-chrome}"
MCP_PORT="${SMOKE_MCP_PORT:-18931}"; CDP_PORT="${SMOKE_CDP_PORT:-19222}"; SITE_PORT="${SMOKE_SITE_PORT:-18951}"
export MCP_URL="http://127.0.0.1:${MCP_PORT}/mcp" CDP_URL="http://127.0.0.1:${CDP_PORT}" SITE_URL="http://127.0.0.1:${SITE_PORT}/"
WORK="$(mktemp -d)"
CHROME_PID=""; SITE_PID=""
cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  [ -n "$CHROME_PID" ] && kill "$CHROME_PID" 2>/dev/null || true
  [ -n "$SITE_PID" ] && kill "$SITE_PID" 2>/dev/null || true
  sleep 1; rm -rf "$WORK"
}
trap cleanup EXIT
fail() { echo "SMOKE FAIL: $*" >&2; docker logs "$NAME" 2>&1 | tail -30 >&2 || true; exit 1; }
py() { (cd "$HERE/smoke" && python3 "$@"); }

start_chrome() {
  # a "user" tab is already open: it must never be touched by the tests
  "$CHROME_BIN" --headless=new --user-data-dir="$WORK/profile" --remote-debugging-address=127.0.0.1 \
    --remote-debugging-port="$CDP_PORT" --no-first-run --no-default-browser-check --disable-dev-shm-usage \
    --disable-gpu --window-size=1280,800 "${SITE_URL}user.html" >"$WORK/chrome.log" 2>&1 &
  CHROME_PID=$!
  # a cold start on a CI runner can take well over 10 s
  for _ in $(seq 1 120); do curl -fsS -m 1 "$CDP_URL/json/version" >/dev/null 2>&1 && return 0; sleep 0.5; done
  tail -20 "$WORK/chrome.log" >&2
  fail "chrome did not start within 60 s"
}

python3 -m http.server "$SITE_PORT" --bind 127.0.0.1 --directory "$HERE/smoke/site" >"$WORK/site.log" 2>&1 &
SITE_PID=$!
start_chrome
echo "ok: chrome $(curl -fsS "$CDP_URL/json/version" | python3 -c 'import json,sys; print(json.load(sys.stdin)["Browser"])')"

docker run -d --name "$NAME" --network host --read-only --tmpfs /tmp:uid=1000,gid=1000 \
  -e BROWSER_URL="$CDP_URL" -e MCP_HOST=127.0.0.1 -e MCP_PORT="$MCP_PORT" "$IMG" >/dev/null
for _ in $(seq 1 60); do
  docker logs "$NAME" 2>&1 | grep "starting server on port" >/dev/null && break
  sleep 1
done
docker logs "$NAME" 2>&1 | grep "starting server on port" >/dev/null || fail "server did not start"
echo "ok: listening (read-only root, /tmp tmpfs)"

py - <<'PY' || fail "tool list"
from mcpclient import rpc
names = {t["name"] for t in rpc("tools/list", {})["result"]["tools"]}
need = {"new_page", "list_pages", "close_page", "take_snapshot", "take_screenshot", "click", "click_at", "evaluate_script", "wait_for"}
assert len(names) == 33 and need <= names, (len(names), sorted(need - names))
print("ok: tools/list = %d (incl. click_at: --experimental-vision)" % len(names))
PY

code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${MCP_PORT}/sse")
[ "$code" = 404 ] || fail "SSE endpoint should be off, got $code"
echo "ok: /sse off"

u=$(docker exec "$NAME" /nodejs/bin/node -e 'process.stdout.write(String(process.getuid()))')
[ "$u" = 1000 ] || fail "uid $u != 1000"
echo "ok: uid 1000"

if docker exec "$NAME" /bin/sh -c true >/dev/null 2>&1; then fail "/bin/sh exists"; fi
echo "ok: no shell"

docker exec "$NAME" /nodejs/bin/node -e '
const n = ["CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS", "CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS", "CHROME_DEVTOOLS_MCP_NO_CONFIG_DISCOVERY"];
process.exit(n.every((k) => process.env[k] === "1") ? 0 : 1)' || fail "update check / usage statistics / config discovery not disabled"
echo "ok: update check, usage statistics, config discovery off"

py isolation.py > "$WORK/isolation.jsonl" || { cat "$WORK/isolation.jsonl" >&2; fail "isolation"; }
tail -1 "$WORK/isolation.jsonl"
echo "ok: isolation"

# file: navigations are refused (--no-file-navigations)
py - <<'PY' || fail "file: navigation not refused"
from mcpclient import call
err, txt, _ = call("new_page", {"url": "file:///etc/passwd", "background": True})
assert err, txt
print("ok: file: URL refused")
PY

# browser restart: the next call reconnects by itself and says page ids changed
kill "$CHROME_PID"; wait "$CHROME_PID" 2>/dev/null || true; CHROME_PID=""
start_chrome
py - <<'PY' || fail "reconnect after browser restart"
from mcpclient import call
err, txt, _ = call("list_pages")
assert not err and "Page ids have changed" in txt, txt
print("ok: reconnected after browser restart (reply says page ids changed)")
PY
[ "$(docker inspect -f '{{.RestartCount}} {{.State.Running}}' "$NAME")" = "0 true" ] || fail "container restarted"
echo "SMOKE PASS"
