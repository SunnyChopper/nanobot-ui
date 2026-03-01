FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install Node.js 20 for the WhatsApp bridge
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg git && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get purge -y gnupg && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Install Brave Browser
RUN curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg] https://brave-browser-apt-release.s3.brave.com/ stable main" > /etc/apt/sources.list.d/brave-browser-release.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends brave-browser && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p nanobot bridge && touch nanobot/__init__.py && \
    uv pip install --system --no-cache . && \
    rm -rf nanobot bridge

# Copy Python app and bridge package.json only (so npm layer can be cached)
COPY nanobot/ nanobot/
COPY bridge/package*.json bridge/
RUN uv pip install --system --no-cache .

# Install bridge deps: npm ci when lockfile present (fast), else npm install
WORKDIR /app/bridge
RUN --mount=type=cache,target=/root/.npm \
    (test -f package-lock.json && npm ci --prefer-offline --no-audit --no-fund) || npm install --prefer-offline --no-audit --no-fund
# Copy rest of bridge (tsconfig + source) and build (dest . is /app/bridge)
COPY bridge/tsconfig.json ./
COPY bridge/src ./src/
RUN npm run build
WORKDIR /app

# Create config directory (used when NANOBOT_HOME is not set)
RUN mkdir -p /root/.nanobot

# Entrypoint sets NANOBOT_HOME so config/workspace are found at /workspace (mount point).
# Needed because docker run -e can be unreliable on Windows.
# Strip CR (Windows line endings) so shebang is #!/bin/sh not #!/bin/sh\r
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# Gateway default port
EXPOSE 18790

ENTRYPOINT ["/entrypoint.sh"]
CMD ["status"]
