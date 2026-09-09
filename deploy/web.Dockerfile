FROM node:22-bookworm-slim AS build
WORKDIR /app/clients/web
COPY clients/web/package*.json ./
RUN npm ci
COPY clients/web/ ./
RUN npm run build

FROM nginxinc/nginx-unprivileged:stable-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/clients/web/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1
