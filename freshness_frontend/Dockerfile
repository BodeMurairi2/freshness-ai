# Frontend: build the React app, then serve the static files with nginx

# ---------- build
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# the API address and limits are baked into the build (Vite replaces import.meta.env.VITE_*)
ARG VITE_API_URL=https://api.freshness.bodemurairi.me
ARG VITE_DECISION_THRESHOLD=0.75
ARG VITE_RETRAIN_MIN_IMAGES=4
ARG VITE_RETRAIN_MAX_EPOCHS=10
ENV VITE_API_URL=$VITE_API_URL \
    VITE_DECISION_THRESHOLD=$VITE_DECISION_THRESHOLD \
    VITE_RETRAIN_MIN_IMAGES=$VITE_RETRAIN_MIN_IMAGES \
    VITE_RETRAIN_MAX_EPOCHS=$VITE_RETRAIN_MAX_EPOCHS
RUN npm run build

# ---------- serve
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
