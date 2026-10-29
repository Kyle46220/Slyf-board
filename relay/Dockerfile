FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY relay.py .
RUN useradd --uid 10001 --create-home relay && mkdir /data && chown relay /data
USER relay
VOLUME /data
CMD ["python", "relay.py"]
