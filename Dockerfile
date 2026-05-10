FROM python:3.11-slim

# =========================================================
# SYSTEM DEPENDENCIES (required for spaCy + Presidio)
# =========================================================
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# =========================================================
# WORKDIR
# =========================================================
WORKDIR /app

# =========================================================
# INSTALL PYTHON DEPENDENCIES
# =========================================================
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =========================================================
# DOWNLOAD SPACY MODEL 
# =========================================================
RUN python -m spacy download en_core_web_sm

# =========================================================
# COPY APPLICATION CODE
# =========================================================
COPY . .

# =========================================================
# ENVIRONMENT SETTINGS
# =========================================================
ENV PYTHONUNBUFFERED=1

# =========================================================
# START SERVER
# =========================================================
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
