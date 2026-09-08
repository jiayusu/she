FROM node:22-bookworm-slim AS build
WORKDIR /app/backend/device_gateway
COPY backend/device_gateway/package*.json ./
RUN npm ci
COPY backend/device_gateway/tsconfig*.json ./
COPY backend/device_gateway/src ./src
RUN npm run build && npm prune --omit=dev

FROM node:22-bookworm-slim
ENV NODE_ENV=production HOST=0.0.0.0 PORT=8788
WORKDIR /app/backend/device_gateway
COPY --from=build /app/backend/device_gateway/package.json ./
COPY --from=build /app/backend/device_gateway/node_modules ./node_modules
COPY --from=build /app/backend/device_gateway/dist ./dist
COPY shared/contracts/v1 /app/shared/contracts/v1
USER node
EXPOSE 8788
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s CMD node -e "fetch('http://127.0.0.1:8788/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "dist/index.js"]
