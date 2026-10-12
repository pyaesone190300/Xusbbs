FROM python:3.10-slim

# Install FFmpeg for video/audio processing
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Expose port for Render
EXPOSE 5000

CMD ["python", "app.py"]
