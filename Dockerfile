# Fusion Coloring — single-file app, stdlib only (Pillow optional, for cover upscaling).
FROM python:3.12-slim
WORKDIR /app
COPY folio_press.py .
# Pillow enables cover-art 300 DPI upscaling on the server.
RUN pip install --no-cache-dir pillow
ENV PORT=8765
EXPOSE 8765
CMD ["python3", "folio_press.py"]
