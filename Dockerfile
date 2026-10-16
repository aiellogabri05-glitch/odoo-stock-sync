FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# The app uses only the standard library at runtime.
COPY app ./app
COPY config.toml ./config.toml

CMD ["python", "-m", "app.sync"]
