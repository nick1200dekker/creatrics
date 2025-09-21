FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables for production
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV FLASK_ENV=production

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make sure the auth directory exists
RUN mkdir -p /app/app/system/auth
RUN touch /app/app/system/auth/__init__.py

# Expose port 8080
EXPOSE 8080

# Run the application with gunicorn - production settings
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 wsgi:app