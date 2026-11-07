# ── Build the SPA, then serve it from nginx ──────────────────────────────────
# Two stages, so node and the dev dependencies never reach the runtime image:
# what ships is nginx plus a few hundred KB of static files.
#
# NOTE: the build context is the REPOSITORY ROOT, not frontend/, because the
# nginx config lives in docker/ and a Dockerfile cannot COPY from above its
# own context. docker-compose.yml sets this; building by hand needs
#     docker build -f frontend/Dockerfile .
# from the repository root.

FROM node:20-alpine AS build
WORKDIR /app

# Dependencies install in their own layer, keyed on the lockfile, so editing
# a component does not re-run npm ci.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Empty means "same origin": nginx proxies /api, so the bundle carries no
# absolute backend URL and the image is not tied to one deployment.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1
