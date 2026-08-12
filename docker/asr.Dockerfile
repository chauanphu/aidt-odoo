# docker/asr.Dockerfile
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y python3 python3-pip ffmpeg curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/asr_fastapi/requirements.txt .
RUN pip3 install -r requirements.txt

COPY docker/asr_fastapi/ /app/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

