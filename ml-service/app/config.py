import os

STUB = os.getenv("ML_STUB", "1") == "1"

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed-for-vllm")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

MODELS_DIR = os.getenv("MODELS_DIR", "models")
MANUALS_DIR = os.getenv("MANUALS_DIR", "manuals")

ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))

# Placeholder list. Replace with the real classes of the chosen dataset
# and update both contracts (see contracts/README.md, "Open decisions").
DEFECT_TYPES = ["scratch", "crack", "dent", "contamination", "color"]

MAX_IMAGE_BYTES = 10 * 1024 * 1024
