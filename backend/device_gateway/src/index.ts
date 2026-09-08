import { createGateway } from "./app.js";


const port = Number(process.env.PORT ?? "8788");
const allowedOrigins = (process.env.SHE_ALLOWED_ORIGINS ?? "")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);
const gateway = await createGateway({ host: "127.0.0.1", port, allowedOrigins });
console.log(`SHE Device Gateway listening at ${gateway.url}`);
if (allowedOrigins.length > 0) {
  console.log(`CORS allowlist: ${allowedOrigins.join(", ")}`);
}

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, async () => {
    await gateway.close();
    process.exit(0);
  });
}
