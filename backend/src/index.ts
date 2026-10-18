// Backend API. Contract: contracts/backend.openapi.yaml
import cors from "cors";
import express, { type NextFunction, type Request, type Response } from "express";
import multer from "multer";

import { sql } from "./db.js";
import { docsRouter } from "./docs.js";
import { inspectionsRouter } from "./inspections.js";
import { mlHealth } from "./ml-client.js";

const app = express();
const api = express.Router();

app.use(cors());
app.use(express.json());

api.get("/health", async (_req: Request, res: Response) => {
  let ml_service: "ok" | "degraded" | "down" = "down";
  let ml_device: string | undefined;
  try {
    const h = await mlHealth();
    ml_service = h.status;
    ml_device = h.device ?? undefined;
  } catch {
    // ML service unreachable
  }
  let dbOk = true;
  try {
    await sql`select 1`;
  } catch {
    dbOk = false;
  }
  res.json({ status: dbOk && ml_service === "ok" ? "ok" : "degraded", ml_service, ml_device });
});

api.use(inspectionsRouter);

// TODO(backend): remaining routes from the contract
const todo = (_req: Request, res: Response) => res.status(501).json({ error: "Not implemented yet" });
api.post("/inspections/:id/explain", todo);
api.post("/inspections/:id/chat", todo);
api.post("/inspections/:id/decision", todo);
api.get("/stats", todo);
api.get("/simulator", todo);
api.post("/simulator/start", todo);
api.post("/simulator/stop", todo);
api.get("/events", todo);

app.use("/api", api);
app.use(docsRouter()); // http://localhost:3000/docs

// Errors always answer JSON in the contract's `Error` shape, never Express's HTML page.
app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
  if (err instanceof multer.MulterError) {
    if (err.code === "LIMIT_FILE_SIZE") return res.status(413).json({ error: "image is larger than 10 MB" });
    return res.status(400).json({ error: err.message, detail: err.field });
  }
  const status = (err as { status?: number }).status ?? 500; // e.g. 400 from express.json on bad JSON
  if (status >= 500) console.error(err);
  res.status(status).json({ error: status >= 500 ? "Internal error" : String((err as Error).message), detail: String(err) });
});

const port = Number(process.env.PORT ?? 3000);
app.listen(port, () => console.log(`backend listening on :${port}`));
