FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY model_comparison_app/requirements.txt ./model_comparison_app/requirements.txt
RUN python -m pip install --no-cache-dir -r model_comparison_app/requirements.txt

COPY common ./common
COPY model_comparison_app ./model_comparison_app

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "model_comparison_app/app.py"]