# Dockerfile - Data Quality Scanner
# Standardized, reproducible container environment for Data Quality Scanner

FROM python:3.12-slim

# Prevent Python from writing .pyc files to disk and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=offscreen

WORKDIR /app

# Install minimal system runtime libraries for PySide6/Qt and SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libdbus-1-3 \
    libfontconfig1 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxkbcommon-x11-0 \
    libxrender1 \
    libxi6 \
    libegl1 \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create volume mount directories for external persistence
RUN mkdir -p /app/data /app/config /app/reports

# Declare persistent mount points
VOLUME ["/app/data", "/app/config", "/app/reports"]

# Default entrypoint: Run the Data Quality Scanner
CMD ["python", "main.py"]
