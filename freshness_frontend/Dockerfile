# Frontend: build the React app, then serve the static files with nginx

# ---------- build
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# the API address is baked into the build (Vite replaces import.meta.env.VITE_API_URL)
ARG VITE_API_URL=https://api.freshness.bodemurairi.me
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---------- serve
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
