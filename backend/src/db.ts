import postgres from "postgres";

// Tables are created by db/init.sql when the Postgres container first starts.
export const sql = postgres(
  process.env.DATABASE_URL ?? "postgres://app:app@localhost:5432/inspections",
  { max: 10 },
);
