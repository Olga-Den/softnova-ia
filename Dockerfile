# Obraz aplikacji SoftNova IAM
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY dostep ./dostep
COPY aplikacja ./aplikacja

# Aplikacja nie działa jako root
RUN useradd --create-home --uid 1000 aplikacja
USER aplikacja

EXPOSE 8000
CMD ["uvicorn", "aplikacja.main:app", "--host", "0.0.0.0", "--port", "8000"]
