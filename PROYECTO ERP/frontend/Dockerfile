# syntax=docker/dockerfile:1.7
# Multi-stage: build con Node + serve estatico con nginx
# Alternativa al deploy en Cloudflare Pages / Vercel cuando se prefiere VPS o Fly.

# === STAGE 1: build ===
FROM node:20-alpine AS build

WORKDIR /app

# Cache de deps - copiamos solo package*.json primero
COPY package*.json ./
RUN npm ci

# Copy source y buildear
COPY . .

# VITE_API_URL apunta al mismo host (reverse proxy nginx hace /api -> backend).
# En setups con backend en otro dominio, override en build time:
#   docker build --build-arg VITE_API_URL=https://api.jarvis-core.com .
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# === STAGE 2: serve ===
FROM nginx:alpine

# Copiamos config y build artifact
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Healthcheck simple
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
