# Stub / CPU image. On the AMD GPU machine, use a ROCm PyTorch base image instead
# (e.g. FROM rocm/pytorch:<tag>) and run `uv sync --extra ml` -- see README.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Dependencies first, so code changes don't reinstall them
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY app ./app
COPY manuals ./manuals

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
