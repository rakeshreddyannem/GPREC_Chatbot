# Lightweight Python 3.11 slim base for Hugging Face Space deployment
FROM python:3.11-slim

# Prevent Python from writing bytecode and enable immediate output flushing
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/home/appuser/.cache/huggingface \
    PORT=7860

# Install minimal OS dependencies:
# - curl: needed for container healthcheck
# - libgomp1: OpenMP runtime needed by PyTorch and FAISS on Debian slim
# Note: tesseract-ocr is excluded because OCR is only used in offline crawling/PDF ingest, not at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user (UID 1000 standard for Hugging Face Spaces)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /home/appuser/.cache/huggingface && \
    chown -R appuser:appuser /home/appuser /app

WORKDIR /app

# Pre-install CPU-only PyTorch build to keep image lightweight (saves ~1.5GB vs CUDA build)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install pinned runtime Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the sentence-transformers model during image build
# This ensures the first user query responds instantly without downloading weights at runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code, pre-computed vectorstore, database, and UI assets
COPY --chown=appuser:appuser . .

# Ensure app directory permissions are owned by non-root user
RUN chown -R appuser:appuser /app /home/appuser

# Switch to non-root user for secure execution
USER appuser

# Hugging Face Spaces requires exposing port 7860
EXPOSE 7860

# Built-in Streamlit healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:7860/_stcore/health || exit 1

# Start command with detailed flag explanations:
# --server.port 7860: Hugging Face Spaces routes inbound external traffic specifically to port 7860
# --server.address 0.0.0.0: Binds to all network interfaces so traffic from outside the container can reach Streamlit
# --server.headless true: Disables attempting to launch an OS GUI browser window on container startup
# --server.enableCORS false: Disables CORS checks so the app can be embedded safely in Hugging Face iframes and proxy domains
# --server.enableXsrfProtection false: Disables XSRF cookie verification which often fails across reverse proxies and websocket handshakes in Hugging Face Spaces
ENTRYPOINT ["streamlit", "run", "app.py", \
    "--server.port", "7860", \
    "--server.address", "0.0.0.0", \
    "--server.headless", "true", \
    "--server.enableCORS", "false", \
    "--server.enableXsrfProtection", "false"]
