ARG NODE_IMAGE=node:22.14.0-bookworm-slim
ARG NGINX_IMAGE=nginx:1.27.4-bookworm
FROM ${NODE_IMAGE} AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM ${NGINX_IMAGE}

ENV BACKEND_UPSTREAM=http://backend:8000 \
    GRADELENS_WRITE_API_KEY="" \
    NGINX_ENVSUBST_FILTER="^(BACKEND_UPSTREAM|GRADELENS_WRITE_API_KEY)$"

COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD ["wget", "--quiet", "--tries=1", "--spider", "http://127.0.0.1:8080/healthz"]
