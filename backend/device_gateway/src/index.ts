import { createGateway } from "./app.js";


const port = Number(process.env.PORT ?? "8788");
const gateway = await createGateway({ host: "127.0.0.1", port });
console.log(`SHE Device Gateway listening at ${gateway.url}`);

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, async () => {
    await gateway.close();
    process.exit(0);
  });
}
