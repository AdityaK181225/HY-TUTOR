# =============================================================================
# HY-TUTOR — Dockerfile for Web Deployment
# =============================================================================
# Usage:
#   docker build -t hytutor .
#   docker run -p 8501:8501 hytutor
#
# Or deploy to Render.com, Railway.app, Fly.io, etc.
# Users provide their own Gemini API key via the in-app First-Run Wizard.
# =============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies needed by ChromaDB and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Create necessary data directories
RUN mkdir -p data_library/active_workspace \
    data_library/cache \
    data_library/metadata \
    data_library/raw_sources \
    data_library/recovery \
    data_library/subject_workspaces \
    data_library/user_state

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Launch Streamlit
CMD ["streamlit", "run", "interface/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]