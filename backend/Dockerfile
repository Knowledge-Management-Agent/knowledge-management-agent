FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# CPU-only torch first (sentence-transformers' dependency) -- keeps the
# image far smaller than the default CUDA-enabled wheel, which isn't
# usable/needed on the EKS nodes anyway.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Bake the local embedding model's weights into the image so pods never
# depend on reaching huggingface.co at runtime/restart -- only the PVC
# (chroma data) persists across restarts, not a HF cache dir.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY app ./app

ENV CHROMA_PERSIST_DIR=/data/chroma
VOLUME /data/chroma

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
