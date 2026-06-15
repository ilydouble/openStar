# Build context: openStar2/ root (includes both pi/ and pi-source-service/)

# Stage 1: Build @earendil-works/pi-ai from source
FROM node:22-alpine AS build-ai
RUN npm install -g @typescript/native-preview@7.0.0-dev.20260120.1
WORKDIR /pkg/ai
COPY pi/packages/ai/package.json ./
RUN npm install --ignore-scripts
COPY pi/packages/ai/src ./src
COPY pi/packages/ai/tsconfig.build.json ./
COPY pi/tsconfig.base.json /tsconfig.base.json
RUN tsgo -p tsconfig.build.json

# Stage 2: Build @earendil-works/pi-agent-core from source
FROM node:22-alpine AS build-agent
RUN npm install -g @typescript/native-preview@7.0.0-dev.20260120.1
WORKDIR /pkg/agent
COPY pi/packages/agent/package.json ./
RUN npm install --ignore-scripts
COPY --from=build-ai /pkg/ai/dist ./node_modules/@earendil-works/pi-ai/dist
COPY --from=build-ai /pkg/ai/package.json ./node_modules/@earendil-works/pi-ai/package.json
COPY --from=build-ai /pkg/ai/dist /pkg/ai/dist
COPY pi/packages/agent/src ./src
COPY pi/packages/agent/tsconfig.build.json ./
COPY pi/tsconfig.base.json /tsconfig.base.json
RUN tsgo -p tsconfig.build.json

# Stage 3: Build @earendil-works/pi-tui from source
FROM node:22-alpine AS build-tui
RUN npm install -g @typescript/native-preview@7.0.0-dev.20260120.1
WORKDIR /pkg/tui
COPY pi/packages/tui/package.json ./
RUN npm install --ignore-scripts
# pi-tui relies on root node_modules/@types/node via tsconfig.base.json "types":["node"]
RUN npm install --ignore-scripts @types/node
COPY pi/packages/tui/src ./src
COPY pi/packages/tui/tsconfig.build.json ./
COPY pi/tsconfig.base.json /tsconfig.base.json
RUN tsgo -p tsconfig.build.json

# Stage 4: Build @earendil-works/pi-coding-agent from source
FROM node:22-alpine AS build-coding-agent
RUN npm install -g @typescript/native-preview@7.0.0-dev.20260120.1
WORKDIR /pkg/coding-agent
COPY pi/packages/coding-agent/package.json ./
RUN npm install --ignore-scripts
# Place built deps in node_modules for npm resolution
COPY --from=build-ai /pkg/ai/dist ./node_modules/@earendil-works/pi-ai/dist
COPY --from=build-ai /pkg/ai/package.json ./node_modules/@earendil-works/pi-ai/package.json
COPY --from=build-agent /pkg/agent/dist ./node_modules/@earendil-works/pi-agent-core/dist
COPY --from=build-agent /pkg/agent/package.json ./node_modules/@earendil-works/pi-agent-core/package.json
COPY --from=build-tui /pkg/tui/dist ./node_modules/@earendil-works/pi-tui/dist
COPY --from=build-tui /pkg/tui/package.json ./node_modules/@earendil-works/pi-tui/package.json
# Place built deps at absolute paths matching tsconfig.build.json path mappings
COPY --from=build-ai /pkg/ai/dist /pkg/ai/dist
COPY --from=build-agent /pkg/agent/dist /pkg/agent/dist
COPY --from=build-tui /pkg/tui/dist /pkg/tui/dist
COPY pi/packages/coding-agent/src ./src
COPY pi/packages/coding-agent/tsconfig.build.json ./
COPY pi/tsconfig.base.json /tsconfig.base.json
RUN tsgo -p tsconfig.build.json

# Stage 5: Runtime image
FROM node:22-alpine AS runtime
WORKDIR /app

COPY pi-source-service/package.json ./
RUN npm install --ignore-scripts

# Place pi-ai: dist + all runtime deps (anthropic, openai, etc.)
COPY --from=build-ai /pkg/ai/dist ./node_modules/@earendil-works/pi-ai/dist
COPY --from=build-ai /pkg/ai/package.json ./node_modules/@earendil-works/pi-ai/package.json
COPY --from=build-ai /pkg/ai/node_modules ./node_modules

# Place pi-agent-core: dist + runtime deps
COPY --from=build-agent /pkg/agent/dist ./node_modules/@earendil-works/pi-agent-core/dist
COPY --from=build-agent /pkg/agent/package.json ./node_modules/@earendil-works/pi-agent-core/package.json
COPY --from=build-agent /pkg/agent/node_modules ./node_modules

# Place pi-tui: dist + runtime deps
COPY --from=build-tui /pkg/tui/dist ./node_modules/@earendil-works/pi-tui/dist
COPY --from=build-tui /pkg/tui/package.json ./node_modules/@earendil-works/pi-tui/package.json
COPY --from=build-tui /pkg/tui/node_modules ./node_modules

# Place pi-coding-agent: dist + runtime deps
COPY --from=build-coding-agent /pkg/coding-agent/dist ./node_modules/@earendil-works/pi-coding-agent/dist
COPY --from=build-coding-agent /pkg/coding-agent/package.json ./node_modules/@earendil-works/pi-coding-agent/package.json
COPY --from=build-coding-agent /pkg/coding-agent/node_modules ./node_modules

COPY pi-source-service/tsconfig.json ./
COPY pi-source-service/src ./src

# Install git — required by pi-source-service for per-file change tracking
# (ensureGitRepo / gitCommit helpers used by the sandboxed write/edit tools).
# Identity is passed inline per-command (-c flag) so no global config needed.
RUN apk add --no-cache git \
 # Allow git to operate on directories owned by any user (workspace files are
 # extracted by the icore-agent backend container, which may run as a different
 # UID). This is safe inside the container — the sandbox boundary is enforced
 # by makeContainmentGuard, not git ownership checks.
 && git config --system safe.directory '*'

# Sandbox workspace directory for agent tools
RUN mkdir -p /workspace

EXPOSE 11002
CMD ["node", "--import", "tsx/esm", "src/server.ts"]
