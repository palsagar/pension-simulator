FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data/countries ./data/countries
RUN uv sync --locked --no-dev

ENV PENSION_DATA_DIR=/app/data/countries
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "--factory", "pension_simulator.api:create_app", "--host", "0.0.0.0", "--port", "8000"]
