FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY seed/ ./seed/
RUN pip install --no-cache-dir -e '.[dev]'

COPY tests/ ./tests/
COPY --from=web /web/dist ./web/dist

ENV FOODBREW_DB_PATH=/data/foodbrew.db \
    FOODBREW_WEB_DIST=/app/web/dist

EXPOSE 8000
CMD ["uvicorn", "foodbrew.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
