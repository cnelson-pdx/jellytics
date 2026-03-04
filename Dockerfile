FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" 2>/dev/null || pip install --no-cache-dir \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.29.0" \
    "sqlalchemy>=2.0.0" \
    "aiosqlite>=0.19.0" \
    "apprise>=1.8.0" \
    "jinja2>=3.1.0" \
    "pyyaml>=6.0" \
    "httpx>=0.27.0" \
    "python-dotenv>=1.0.0" \
    "pydantic>=2.0.0" \
    "pydantic-settings>=2.0.0" \
    "python-multipart>=0.0.9"

COPY . .
RUN pip install --no-cache-dir -e .

# Data directory for SQLite
RUN mkdir -p /data
ENV DATABASE_URL=sqlite+aiosqlite:////data/jellytics.db

EXPOSE 8234

CMD ["python", "-m", "jellytics.main"]
