# Servidor do mural (FastAPI). Não recebe votos: só manifesto, chaves públicas e boletins assinados.
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 urna
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY exemplos ./exemplos
RUN pip install --no-cache-dir ".[servidor]"

USER urna
VOLUME ["/dados"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/saude')" || exit 1
ENTRYPOINT ["urna3g", "servidor", "--dados", "/dados", "--host", "0.0.0.0", "--porta", "8000"]
