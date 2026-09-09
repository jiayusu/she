# Parent Web

Layer: Web. React parent app for today, reports, device settings, family controls,
and an optional read-only Embodied Language RPG task card. It calls Device Gateway
APIs and decodes shared contract v1 responses; it does not make teaching decisions,
advance story nodes, or write world/mastery state. The current Gateway provides demo
data and production family identity is not implemented.

## Read-only RPG task card

The Today page can read:

```text
GET /v1/rpg/state?child_id=...&session_id=...
```

The client strictly decodes `rpg-quest-summary.schema.json` and shows only the
current phase, reviewed world role, target expression, virtual inventory, next
quest, and delivery status. It does not receive or render a child's utterance,
Speech Act evidence, raw perception, debug prompts, or the full Memory response.
There is no RPG write method in `AppApi`.

Because login and production household authorization are not available, the Web
client makes this request only when both build-time demo values are explicitly set:

```sh
VITE_SHE_RPG_CHILD_ID=child-demo
VITE_SHE_RPG_SESSION_ID=session-demo
```

If either value is absent or blank, the request is not made and the task card is
not displayed. These variables are a local/demo integration aid, not an identity
or authorization mechanism.

## Run and test

From the repository root:

```sh
npm ci --prefix clients/web
npm run dev --prefix clients/web
npm test --prefix clients/web
npm run typecheck --prefix clients/web
npm run build --prefix clients/web
```

The dev server proxies to Gateway at localhost:8788. `SHE_GATEWAY_URL` overrides the
proxy target. Container deployment instructions are in `deploy/README.md` (relative
to repository root). API contracts are in `shared/contracts/v1`.
