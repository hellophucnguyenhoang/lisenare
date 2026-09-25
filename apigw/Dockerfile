# Use a Python base image
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv from the official distribution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy ONLY apigw package definitions
COPY pyproject.toml uv.lock ./

# Install project dependencies securely
RUN uv sync --frozen --no-dev && rm -rf /root/.cache/uv

# Copy the apigw source code
COPY . .

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="."

RUN chmod +x start.sh

ENV PORT=8000
EXPOSE 8000

# start API Gateway server
CMD ["./start.sh"]
