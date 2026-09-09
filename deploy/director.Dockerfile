FROM node:22-bookworm-slim
WORKDIR /app/agents/director
COPY agents/director/package*.json ./
RUN npm ci
COPY agents/director/src ./src
COPY agents/director/config ./config
COPY agents/director/content ./content
RUN mkdir data && chown node:node data
ENV PORT=8790 DATA_DIR=/app/agents/director/data
USER node
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s CMD node -e "fetch('http://127.0.0.1:8790/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["npm", "start"]
