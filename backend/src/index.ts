// Backend API. Contract: contracts/backend.openapi.yaml
import cors from "cors";
import express, { type Request, type Response } from "express";
import multer from "multer";

import { sql } from "./db.js";
import { docsRouter } from "./docs.js";
import { MlError, mlHealth, mlInspect } from "./ml-client.js";

const app = express();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });
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

// Day-1 spike: proves frontend -> backend -> ML works. Not yet saved to the database.
// TODO(backend): save image + result, return the full `Inspection` shape from the contract.
api.post("/inspections", upload.single("image"), async (req: Request, res: Response) => {
  if (!req.file) return res.status(400).json({ error: "image is required" });
  try {
    const vision = await mlInspect(req.file.buffer, req.file.originalname, req.file.mimetype, req.body.part_type);
    res.status(201).json({ vision });
  } catch (e) {
    const status = e instanceof MlError ? 502 : 500;
    res.status(status).json({ error: "ML service failed", detail: String(e) });
  }
});

// TODO(backend): remaining routes from the contract
const todo = (_req: Request, res: Response) => res.status(501).json({ error: "Not implemented yet" });
api.get("/inspections", todo);
api.get("/inspections/:id", todo);
api.get("/inspections/:id/image", todo);
api.get("/inspections/:id/mask", todo);
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

const port = Number(process.env.PORT ?? 3000);
app.listen(port, () => console.log(`backend listening on :${port}`));
