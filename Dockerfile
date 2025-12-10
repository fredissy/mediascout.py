FROM python:3.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies (for Pillow)
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates/ templates/

# Create volume mount points
VOLUME ["/media"]

# Expose port
EXPOSE 8000

# Set environment variables with defaults
ENV MEDIA_DIRECTORIES=/media/movies
ENV FILE_EXTENSIONS=mkv,mp4,avi,mov
ENV TMDB_API_KEY=""
ENV TMDB_LOCALE=en-US

# Run the application
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "8000"]
