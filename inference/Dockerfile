# Use a Python base image
FROM python:3.12-slim-bookworm

# Install your complete AI processing system toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    g++ \
    cmake \
    ffmpeg \
    espeak-ng \
    libespeak-ng-dev \
    curl \
    zstd \
    libenchant-2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama locally inside the AI container
RUN curl -fsSL https://ollama.com/install.sh | sh

# Install uv from the official distribution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy ONLY inference package definitions
COPY pyproject.toml uv.lock ./

# Install ML weights and requirements 
RUN uv sync --frozen --no-dev && rm -rf /root/.cache/uv

# Copy the inference source code
COPY . .

# Background bake your local models during the build process
RUN ollama serve & \
    OLLAMA_PID=$! && \
    sleep 3 && \
    ollama pull mahonzhan/all-MiniLM-L6-v2 && \
    ollama pull gemma3:1b && \
    kill $OLLAMA_PID && \
    sleep 2

# Add the environment targets for your text-to-phoneme synthesizer 
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="."

ENV ESPEAK_DATA_PATH="/usr/lib/x86_64-linux-gnu/espeak-ng-data"
ENV PHONEMIZER_ESPEAK_PATH="/usr/bin/espeak-ng"
ENV PHONEMIZER_ESPEAK_LIBRARY="/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1"

RUN chmod +x start.sh

ENV PORT=8001
EXPOSE 8001

# start Ollama and Inference server
CMD ["./start.sh"]