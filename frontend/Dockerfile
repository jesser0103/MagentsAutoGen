# Multi-stage build for Next.js frontend
FROM node:22-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN apk add --no-cache python3 make g++
RUN npm ci
# npm ci can skip platform-specific optional SWC binaries when the lockfile
# was generated on another OS; install the musl binary Next.js needs on Alpine.
RUN npm install --no-save @next/swc-linux-x64-musl@14.2.5

# ---- Auth migrate + first-admin seed (Compose service `auth-init`) ----
FROM deps AS auth-init

COPY . .
CMD ["npx", "tsx", "scripts/bootstrap-admin.ts"]

# ---- Next.js production build ----
FROM deps AS builder

COPY . .
ARG INTERNAL_API_URL=http://api:8000
ENV INTERNAL_API_URL=${INTERNAL_API_URL}
RUN mkdir -p public
RUN npm run build

# ---- Runtime ----
FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
