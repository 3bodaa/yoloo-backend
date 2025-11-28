FROM python:3.10-slim

# ---- Prevent prompts ----
ENV DEBIAN_FRONTEND=noninteractive

# ---- Work Directory ----
WORKDIR /app

# ---- Install system libs required for aiortc + OpenCV ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libavformat58 \
    libavcodec58 \
    libavdevice58 \
    libavfilter7 \
    libswresample3 \
    libswscale5 \
    libavutil56 \
    libopus0 \
    libvpx6 \
    libx264-155 \
    libx265-192 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ---- Install Python libs ----
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---- Copy app files ----
COPY . .

# ---- Expose port ----
EXPOSE 8000

# ---- Run FastAPI server ----
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
