// browser-mcp-image entrypoint: run mcp-proxy in this process, with chrome-devtools-mcp as its one
// stdio child. chrome-devtools-mcp attaches to an already running Chrome / Chromium over CDP and never
// launches a browser itself; every MCP session shares that child, so page ids are global and each
// client must pass its own pageId (--page-id-routing).
//
// Written in JavaScript so the runtime image needs no shell.
//
// env:
//   BROWSER_URL             Chrome DevTools HTTP endpoint (default http://127.0.0.1:9222)
//   MCP_HOST / MCP_PORT     listen address for Streamable HTTP at /mcp (default 0.0.0.0:8931)
//   MCP_REQUEST_TIMEOUT_MS  per request limit inside mcp-proxy (default 900000 = 15 min)
//   MCP_PROXY_API_KEY       optional; when set clients must send X-API-Key (mcp-proxy option)
"use strict";

const path = require("node:path");

const log = (msg) => process.stderr.write(`browser-mcp-image: ${msg}\n`);

// No outbound calls of chrome-devtools-mcp itself: npm update check, usage statistics, config file discovery
for (const name of ["CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS", "CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS", "CHROME_DEVTOOLS_MCP_NO_CONFIG_DISCOVERY"]) {
	if (process.env[name] === undefined) {
		process.env[name] = "1";
	}
}

const browserUrl = process.env.BROWSER_URL || "http://127.0.0.1:9222";
const host = process.env.MCP_HOST || "0.0.0.0";
const port = process.env.MCP_PORT || "8931";
const requestTimeout = process.env.MCP_REQUEST_TIMEOUT_MS || "900000";

const modules = path.join(__dirname, "node_modules");
const child = [
	process.execPath,
	path.join(modules, "chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js"),
	`--browserUrl=${browserUrl}`,
	"--page-id-routing",
	"--experimental-vision",
	"--no-usage-statistics",
	"--no-performance-crux",
	"--no-file-navigations",
];

log(`mcp-proxy on ${host}:${port}/mcp -> chrome-devtools-mcp -> ${browserUrl}`);

// hand over to mcp-proxy in this process (its CLI reads process.argv); it exits when the child exits
process.argv = [process.argv[0], "mcp-proxy",
	"--host", host, "--port", port, "--server", "stream", "--requestTimeout", requestTimeout,
	"--", ...child];
import(path.join(modules, "mcp-proxy/dist/bin/mcp-proxy.mjs")).catch((err) => {
	log(`cannot start mcp-proxy: ${err.stack || err}`);
	process.exit(1);
});
