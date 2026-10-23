# browser-mcp-image

Container image for [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp)
served over MCP Streamable HTTP by [punkpeye/mcp-proxy](https://github.com/punkpeye/mcp-proxy). It attaches to a
Chrome / Chromium that is **already running** (for example a sidecar with a persistent profile) over the DevTools
protocol; the image contains no browser.

- **Unmodified upstream**: `chrome-devtools-mcp` and `mcp-proxy` from npm, every dependency pinned by
  `package-lock.json` (version + sha512); install scripts are not run. This repo only adds an entrypoint.
- **One upstream process for all sessions**: mcp-proxy starts a single chrome-devtools-mcp child and every MCP
  session talks to it. With `--page-id-routing` every page-scoped tool requires a `pageId`, so several clients can
  drive their own tabs in the same browser at the same time without touching each other's (or the user's) tabs.
- **Runtime**: `gcr.io/distroless/nodejs22-debian13` — no shell, no package manager; runs as uid 1000.
- **Image**: `ghcr.io/mouse9527/browser-mcp-image:sha-<short commit>` (linux/amd64; built only from `main`; no `latest`).

| Component | Version |
|---|---|
| chrome-devtools-mcp | 1.12.0 |
| mcp-proxy | 6.7.21 |
| Node.js | 22 (distroless, Debian 13) |

## What the entrypoint does

Starts mcp-proxy in the same process, listening on `MCP_HOST:MCP_PORT` at `/mcp` (Streamable HTTP only; `/sse` is
off), with this child:

```
chrome-devtools-mcp --browserUrl=$BROWSER_URL --page-id-routing --experimental-vision
                    --no-usage-statistics --no-performance-crux --no-file-navigations
```

- `--experimental-vision` adds coordinate tools (`click_at`) for things without an accessibility node (canvas etc.).
- Outbound calls of the MCP server itself are off: npm update check, usage statistics, CrUX lookups and config file
  discovery (`CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS` / `_NO_USAGE_STATISTICS` / `_NO_CONFIG_DISCOVERY` = `1`).
- `file:` URLs cannot be opened with `new_page` / `navigate_page`.
- If chrome-devtools-mcp exits, mcp-proxy exits too (non-zero), so the container runtime restarts it.
- If the **browser** restarts, the next tool call reconnects by itself; its reply starts with
  `Note: the browser was restarted or reconnected since the last call. Page ids have changed.` Clients must then
  find their pages again (`list_pages`); old page ids may point at other tabs.

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `BROWSER_URL` | `http://127.0.0.1:9222` | DevTools HTTP endpoint of the running browser |
| `MCP_HOST` | `0.0.0.0` | Listen address |
| `MCP_PORT` | `8931` | Listen port (`/mcp`) |
| `MCP_REQUEST_TIMEOUT_MS` | `900000` | Per-request limit inside mcp-proxy (long `wait_for` / scripted waits) |
| `MCP_PROXY_API_KEY` | unset | mcp-proxy option: when set, clients must send `X-API-Key` |
| `HOME` | `/tmp/home` | Must be writable |

Writable paths needed with a read-only root filesystem: `/tmp` — mount an `emptyDir` / tmpfs there.

## Run

```bash
# a browser with remote debugging on 127.0.0.1:9222 in the same network namespace (Pod / --network host)
docker run --rm --network host ghcr.io/mouse9527/browser-mcp-image:sha-<short commit>
```

Kubernetes: run it as a second container in the browser's Pod; keep the browser's DevTools port on `127.0.0.1`.

## Security notes

- **No authentication by default**, like most stdio-to-HTTP bridges: anyone who can reach the port can fully drive
  the browser, including its logged-in sessions and arbitrary JavaScript in pages (`evaluate_script`).
  Restrict who can reach it (NetworkPolicy / private network), or set `MCP_PROXY_API_KEY`.
- Never expose the browser's DevTools port itself.

## Upgrading

- **chrome-devtools-mcp / mcp-proxy**: change the versions in `package.json`, then regenerate the lockfile from the
  public npm registry:
  `npm install --package-lock-only --ignore-scripts --omit=dev --registry https://registry.npmjs.org`.
  Check the upstream changelogs for new tools / changed flags and update the expected tool count in `smoke.sh`.
- **Base images**: update the digests in `NODE_IMAGE` / `RUNTIME_IMAGE`; keep both on the same Debian release.

## CI

`.github/workflows/image.yml`: build linux/amd64 → `audit.sh` (no credentials or `.git` in the image, no browser
downloaded, installed versions = `package.json`; file list and hashes uploaded as an artifact) → `smoke.sh` against the
runner's headless Chrome (33 tools, `/sse` off, uid 1000, no shell, telemetry off, two interleaved tasks each on its own
`pageId` with a fresh MCP session per call — `smoke/isolation.py`, `file:` refused, reconnect after a browser restart)
→ push to ghcr from `main` only.

## License

MIT for the files in this repository (`LICENSE`). The image also contains third-party software under its own
licenses; see `NOTICE.md`.
