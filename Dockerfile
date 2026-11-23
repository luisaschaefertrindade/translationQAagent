FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
RUN pip install --no-cache-dir -e .[eval]
COPY eval ./eval
CMD ["python", "eval/run_eval.py"]
