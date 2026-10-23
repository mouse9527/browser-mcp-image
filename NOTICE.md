# Notices

This repository contains only build files (Dockerfile, lockfile, entrypoint, CI, smoke test) under the MIT License
(`LICENSE`). The container image it builds also contains third-party software, unmodified, under the licenses below.

## ChromeDevTools/chrome-devtools-mcp

Source: https://github.com/ChromeDevTools/chrome-devtools-mcp — npm `chrome-devtools-mcp@1.12.0`
License: Apache License 2.0 (the full text ships in the image at `/app/node_modules/chrome-devtools-mcp/LICENSE`).
It bundles third-party code (Puppeteer, Chrome DevTools frontend, Lighthouse, …) under their own licenses, listed in
the package.

## punkpeye/mcp-proxy

Source: https://github.com/punkpeye/mcp-proxy — npm `mcp-proxy@6.7.21`
License: MIT (`/app/node_modules/mcp-proxy/LICENSE`).

Their npm dependencies are installed exactly as pinned in `package-lock.json`; each package's own license file ships
with it under `/app/node_modules/`.

## Node.js runtime

The runtime layer is `gcr.io/distroless/nodejs22-debian13` (Node.js, MIT; Debian packages under their own licenses,
listed in the image under `/usr/share/doc`).
