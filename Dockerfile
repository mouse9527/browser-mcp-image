# browser-mcp-image: ChromeDevTools/chrome-devtools-mcp (unmodified) behind punkpeye/mcp-proxy (Streamable HTTP).
#
# - chrome-devtools-mcp attaches to an existing Chrome / Chromium over CDP (BROWSER_URL); no browser in this image
# - mcp-proxy runs ONE chrome-devtools-mcp child for every MCP session (--page-id-routing keeps sessions apart)
# - both from npm, every dependency pinned by package-lock.json (version + sha512); install scripts not run
# - runtime: distroless Node.js 22 on Debian 13 — no shell, no package manager; entrypoint is JavaScript
# - no upstream code is modified
#
# Upgrade: see README.md ("Upgrading").

ARG NODE_IMAGE=docker.io/library/node:22.23.3-trixie-slim@sha256:154ba2f4d6fec323d28e4f4bb86bba4677f1223391a1979cf521304e03a98dfa
ARG RUNTIME_IMAGE=gcr.io/distroless/nodejs22-debian13:nonroot@sha256:ec2313763dd43931543bd03830466e0c409ce73a487e8d46f10db72d3b816c1c

FROM ${NODE_IMAGE} AS build
WORKDIR /app
COPY package.json package-lock.json ./
# --ignore-scripts: nothing needs them (puppeteer is bundled and never downloads a browser here;
# tldjs' postinstall would only refresh its suffix list over the network)
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund --update-notifier=false \
 && test -f node_modules/chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js \
 && test -f node_modules/mcp-proxy/dist/bin/mcp-proxy.mjs
COPY entrypoint.js ./

FROM ${RUNTIME_IMAGE}
COPY --from=build /app /app
COPY LICENSE NOTICE.md /usr/share/doc/browser-mcp-image/
WORKDIR /app
USER 1000:1000
ENV HOME=/tmp/home \
    TMPDIR=/tmp \
    PATH=/nodejs/bin:/usr/local/bin:/usr/bin:/bin \
    CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS=1 \
    CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS=1 \
    CHROME_DEVTOOLS_MCP_NO_CONFIG_DISCOVERY=1 \
    NODE_ENV=production
EXPOSE 8931
LABEL org.opencontainers.image.source="https://github.com/mouse9527/browser-mcp-image" \
      org.opencontainers.image.description="chrome-devtools-mcp 1.12.0 (unmodified) + mcp-proxy 6.7.21, Streamable HTTP, attaches to an existing Chrome over CDP" \
      org.opencontainers.image.licenses="MIT AND Apache-2.0"
ENTRYPOINT ["/nodejs/bin/node", "/app/entrypoint.js"]
