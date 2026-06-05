# Build context: openStar2/ root (includes both pi/ and pi-source-service/)

# Stage 1: Install tsgo (TypeScript native compiler needed by pi packages)
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
# Place locally built pi-ai for type resolution (tsconfig paths) and runtime
COPY --from=build-ai /pkg/ai/dist ./node_modules/@earendil-works/pi-ai/dist
COPY --from=build-ai /pkg/ai/package.json ./node_modules/@earendil-works/pi-ai/package.json
COPY --from=build-ai /pkg/ai/dist /pkg/ai/dist
COPY pi/packages/agent/src ./src
COPY pi/packages/agent/tsconfig.build.json ./
COPY pi/tsconfig.base.json /tsconfig.base.json
RUN tsgo -p tsconfig.build.json

# Stage 3: Runtime image
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

COPY pi-source-service/tsconfig.json ./
COPY pi-source-service/src ./src

EXPOSE 11002
CMD ["node", "--import", "tsx/esm", "src/server.ts"]
