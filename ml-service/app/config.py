import os

STUB = os.getenv("ML_STUB", "1") == "1"

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8001/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "not-needed-for-vllm")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

MODELS_DIR = os.getenv("MODELS_DIR", "models")
MANUALS_DIR = os.getenv("MANUALS_DIR", "manuals")

ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))

# Dataset: VisA (Amazon), category pcb1, CC BY 4.0. Must match the DefectType / PartType enums
# in contracts/ml-service.openapi.yaml.
PART_TYPE = "pcb1"
DEFECT_TYPES = ["bent", "melt", "scratch", "missing"]  # plus "unknown" when the classifier is unsure

# Below this classifier confidence the defect type is reported as "unknown".
CLASSIFIER_MIN_CONFIDENCE = float(os.getenv("CLASSIFIER_MIN_CONFIDENCE", "0.6"))

MAX_IMAGE_BYTES = 10 * 1024 * 1024
