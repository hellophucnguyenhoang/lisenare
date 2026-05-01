# Use a Python base image
FROM python:3.12-slim-bookworm

# Install system dependencies: ffmpeg and espeak-ng
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    espeak-ng \
    libespeak-ng-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Install uv from the official distroless image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory and copy dependency files
WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN uv sync --frozen --no-dev

# Copy the rest of the application code
COPY . .

# Ensure the start script is executable
RUN chmod +x start.sh

# Add the virtual environment's bin to PATH
ENV PATH="/app/.venv/bin:$PATH"

ENV PORT=8000
EXPOSE 8000

# Start both servers via the script
CMD ["./start.sh"]
