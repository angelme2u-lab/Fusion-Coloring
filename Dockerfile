# Fusion Coloring — single-file app, stdlib only (Pillow optional, for cover upscaling).
FROM python:3.12.16-slim-trixie
WORKDIR /app
COPY folio_press.py .
# Refresh Debian's system trust store for urllib (DSA-6572-1).
# Refuse a stale mirror/base image instead of silently building with old CAs.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates; \
    dpkg --compare-versions "$(dpkg-query -W -f='${Version}' ca-certificates)" ge '20250419+deb13u1'; \
    update-ca-certificates; \
    rm -rf /var/lib/apt/lists/*
# pip has its own certifi bundle. Bootstrap the patched wheel by its published
# SHA-256, with no dependencies or self-version request through the old pip.
RUN python -m pip --disable-pip-version-check install --no-cache-dir --no-index --no-deps \
    "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"
RUN python -c "from pip._vendor import certifi; from pip._vendor.packaging.version import Version; import sys; sys.exit(0 if Version(certifi.__version__) >= Version('2026.10.19') else 'pip has an outdated CA bundle')"
# Pillow enables cover-art 300 DPI upscaling on the server.
RUN python -m pip --disable-pip-version-check install --no-cache-dir pillow \
    && python -m pip check
ENV PORT=8765
EXPOSE 8765
CMD ["python3", "folio_press.py"]
