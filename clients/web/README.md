# Parent Web

Layer: Web. React parent app for today, reports, device settings and family controls.
It calls Device Gateway APIs and decodes shared contract v1 responses; it does not
make teaching decisions or write mastery. The current Gateway provides demo data.

## Run and test

From the repository root:

```sh
npm ci --prefix clients/web
npm run dev --prefix clients/web
npm test --prefix clients/web
npm run typecheck --prefix clients/web
npm run build --prefix clients/web
```

The dev server proxies to Gateway at localhost:8788. SHE_GATEWAY_URL overrides the
proxy target. Container deployment instructions are in `deploy/README.md` (relative
to repository root). API contracts are in `shared/contracts/v1`.
