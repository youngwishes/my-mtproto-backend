FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

COPY src/ .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
