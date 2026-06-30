FROM node:22-alpine AS base
WORKDIR /app

COPY package.json ./
RUN npm install --ignore-scripts

COPY tsconfig.json ./
COPY src ./src

EXPOSE 11002

CMD ["node", "--import", "tsx/esm", "src/server.ts"]
