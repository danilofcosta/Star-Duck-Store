# Multi-stage build for MiniDLNA + Web UI
# Target: ghcr.io/danilofcosta/minidlna-umbrel:latest

# ---- Build Stage ----
FROM debian:bookworm-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libexif-dev \
    libjpeg-dev \
    libid3tag0-dev \
    libflac-dev \
    libvorbis-dev \
    libsqlite3-dev \
    libuuid1 \
    libavformat-dev \
    libavcodec-dev \
    libavutil-dev \
    libswscale-dev \
    libavresample-dev \
    libexpat1-dev \
    libsystemd-dev \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Build MiniDLNA from source (latest features)
WORKDIR /build
ARG MINIDLNA_VERSION=1.3.3
RUN wget -q "https://sourceforge.net/projects/minidlna/files/minidlna/${MINIDLNA_VERSION}/minidlna-${MINIDLNA_VERSION}.tar.gz" \
    && tar xzf "minidlna-${MINIDLNA_VERSION}.tar.gz" \
    && cd "minidlna-${MINIDLNA_VERSION}" \
    && ./configure --prefix=/usr --sysconfdir=/etc \
    && make -j$(nproc) \
    && make install DESTDIR=/build/install

# ---- Runtime Stage ----
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # MiniDLNA runtime deps
    libexif12 \
    libjpeg62-turbo \
    libid3tag0 \
    libflac12 \
    libvorbis0a \
    libsqlite3-0 \
    uuid-runtime \
    libavformat60 \
    libavcodec60 \
    libavutil58 \
    libswscale7 \
    libavresample4 \
    libexpat1 \
    libsystemd0 \
    # Supervisord for process management
    supervisor \
    # Python for Web UI
    python3 \
    python3-pip \
    python3-venv \
    # Utilities
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy MiniDLNA binary and config from builder
COPY --from=builder /build/install/usr/sbin/minidlnad /usr/sbin/minidlnad
COPY --from=builder /build/install/etc/minidlna.conf /etc/minidlna.conf.default

# Create app user
RUN groupadd -g 1000 appuser && useradd -u 1000 -g 1000 -m -s /bin/bash appuser

# Create directories
RUN mkdir -p /config/cache /config/log /run/minidlna /media /app/ui \
    && chown -R appuser:appuser /config /run/minidlna /media /app

# ---- Python Web UI ----
WORKDIR /app
COPY ui/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ui/app.py /app/app.py
COPY ui/templates/ /app/templates/
COPY ui/static/ /app/static/

# Fix permissions
RUN chown -R appuser:appuser /app

# Supervisord config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Default config template (will be copied to /config by init script if not exists)
COPY minidlna.conf.template /etc/minidlna.conf.template

# Entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose ports
# 8200 = MiniDLNA HTTP (descriptions, media streaming)
# 8250 = Web UI
# 1900/udp = SSDP (handled by network_mode: host)
EXPOSE 8200 8250

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8200/status || exit 1

# Run as appuser
USER appuser

# Entry point starts supervisord (manages minidlnad + web UI)
ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf", "-n"]