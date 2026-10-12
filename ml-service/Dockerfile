# Stub / CPU image. For the AMD GPU machine, switch the base to a ROCm PyTorch image,
# e.g. FROM rocm/pytorch:<tag>, and install requirements-ml.txt instead.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY manuals ./manuals

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
