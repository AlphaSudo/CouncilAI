FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    ZEROWALL_MODE=hosted ZEROWALL_DATA_DIR=/var/lib/zerowall
WORKDIR /app
COPY pyproject.toml requirements.lock ./
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY src/ ./src/
RUN python -m pip install --no-cache-dir --no-deps .
COPY config/ ./config/
COPY benchmark/ ./benchmark/
COPY contracts/ ./contracts/
COPY scripts/setup_tokenizers.py ./scripts/setup_tokenizers.py
RUN python scripts/setup_tokenizers.py
COPY --from=web /build/dist/ ./apps/web/dist/
# Settings locates repository assets relative to src/zerowall, as in local installs.
ENV PYTHONPATH=/app/src
RUN useradd --uid 10001 --create-home zerowall \
    && mkdir -p /var/lib/zerowall \
    && chown zerowall:zerowall /var/lib/zerowall
USER zerowall
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/ready',timeout=3)"
CMD ["zerowall", "serve"]
