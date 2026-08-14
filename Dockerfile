FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY seed/ ./seed/
RUN pip install --no-cache-dir -e '.[dev]'

COPY tests/ ./tests/

# M2 replaces this with the uvicorn entrypoint.
CMD ["python", "-c", "from foodbrew.db import create_database; create_database('/data/foodbrew.db'); print('database ready at /data/foodbrew.db')"]
