// Interactive API docs (Swagger UI) at /docs, like FastAPI's /docs.
// Shows the contract (contracts/backend.openapi.yaml), so routes not built yet appear too
// and answer 501 when tried.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { Router } from "express";
import swaggerUi from "swagger-ui-express";
import { parse } from "yaml";

// npm run dev runs from backend/; docker compose mounts the contracts at /contracts.
const contractPath = resolve(process.env.OPENAPI_PATH ?? "../contracts/backend.openapi.yaml");

export function docsRouter(): Router {
  const router = Router();
  let spec: Record<string, unknown>;
  try {
    spec = parse(readFileSync(contractPath, "utf8"));
  } catch (e) {
    console.warn(`API docs disabled: cannot read ${contractPath} (${String(e)})`);
    return router;
  }
  // "Try it out" calls this same server, whatever host port it runs on.
  spec.servers = [{ url: "/api" }];

  router.get("/openapi.json", (_req, res) => res.json(spec));
  router.use("/docs", swaggerUi.serve, swaggerUi.setup(spec));
  return router;
}
