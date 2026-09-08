# Local deployment (no RDK X5 required)

This release packages the existing single-family demonstration app. It is useful for
product review and software integration; it is not a public multi-family service.
Dashboard/report fixtures are mock data. Parent settings and Digital Twin state
reset on Gateway restart. Export/erase remain explicitly simulated. No physical
RDK X5, cloud account, API key, or domain is required.

## Start

Install Docker Desktop (or Docker Engine with Compose), start its engine, then run
from the repository root:

```sh
docker compose up --build --wait
node scripts/deployment-smoke.mjs
```

Open http://localhost:8080. The port binds only to the local machine. The browser
and API share one origin; the Gateway is private to the Compose network. To change
the published port, set SHE_WEB_PORT before starting Compose, and set SHE_SMOKE_URL
to the matching address for the smoke check.

## Operate

```sh
docker compose ps
docker compose logs --tail=100
docker compose down
```

Health checks cover the Gateway and web proxy. Containers restart unless stopped.
No persistent volumes are created because the current parent repository is a demo.
To roll back, check out the previous release and rebuild with the start command.
Do not capture request bodies or credentials in operational logs.

## Public deployment prerequisites

A public release still needs parent authentication and household authorization,
server-side persistent parent state through Shared State APIs, and implemented
privacy export/erase workflows. Those trust boundaries are unchanged by this
packaging. Place any future public service behind TLS and access control only after
those requirements are implemented and reviewed. CORS alone is not authentication.
The Director, knowledge graph, memory service and offline intel pipeline are not
wired into this demo deployment; do not interpret fixture reports as live learning.
iOS requires separate macOS/Xcode build validation. RDK X5 remains pending physical
acceptance, excluded from this release's startup and container checks.

## Development without Docker

```sh
npm ci --prefix backend/device_gateway
npm run build --prefix backend/device_gateway
npm run start:production --prefix backend/device_gateway
```

In another terminal:

```sh
npm ci --prefix clients/web
npm run dev --prefix clients/web
```

Open http://localhost:5173. Run repository checks with `pwsh -File scripts/verify.ps1`.
Gateway HOST defaults to loopback; the container explicitly sets HOST=0.0.0.0.
