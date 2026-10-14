#!/usr/bin/env bash
# Generate app/schemas.py from the ML service contract. Never edit app/schemas.py by hand:
# change contracts/ml-service.openapi.yaml, then run this (from ml-service/):  ./scripts/gen-schemas.sh
set -euo pipefail
cd "$(dirname "$0")/.."
uv run datamodel-codegen \
  --input ../contracts/ml-service.openapi.yaml \
  --input-file-type openapi \
  --output app/schemas.py \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.12 \
  --enum-field-as-literal all \
  --collapse-root-models \
  --use-union-operator \
  --use-standard-collections \
  --use-schema-description \
  --use-field-description \
  --disable-timestamp \
  --custom-file-header "# GENERATED from contracts/ml-service.openapi.yaml by scripts/gen-schemas.sh. Do not edit by hand." \
  --formatters ruff-format ruff-check
