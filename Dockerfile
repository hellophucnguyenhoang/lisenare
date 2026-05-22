# Use a Python base image
FROM python:3.12-slim-bookworm

# Install system dependencies: ffmpeg and espeak-ng
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng-dev \
    curl \
    zstd \
    libenchant-2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Install uv from the official distroless image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory and copy dependency files
WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN uv sync --frozen --no-dev && rm -rf /root/.cache/uv

# Copy the rest of the application code
COPY . .

# Start Ollama, capture its process ID (PID), pull models, and kill it cleanly
RUN ollama serve & \
    OLLAMA_PID=$! && \
    sleep 3 && \
    ollama pull mahonzhan/all-MiniLM-L6-v2 && \
    ollama pull gemma3:1b && \
    kill $OLLAMA_PID && \
    sleep 2

# Ensure the start script is executable
RUN chmod +x start.sh

# Add the virtual environment's bin to PATH
ENV PATH="/app/.venv/bin:$PATH"

ENV PORT=8000
EXPOSE 8000

# Start both servers via the script
CMD ["./start.sh"]
