FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY grader_mcp/requirements.txt /app/grader_mcp/requirements.txt
RUN pip install --no-cache-dir -r /app/grader_mcp/requirements.txt

COPY common /app/common
COPY grader_mcp /app/grader_mcp

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "grader_mcp.server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]