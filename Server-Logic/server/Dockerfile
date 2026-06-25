FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server application
COPY . .

# Expose the API port
EXPOSE 8000

# Default command to run the backend API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
