# Gerbera exports for Umbrel

# Static IP for Gerbera service in the Umbrel Docker network
export APP_GERBERA_IP="${NETWORK_IP}.250"

# Gerbera data directories
export APP_GERBERA_CONFIG_DIR="${EXPORTS_APP_DATA_DIR}/gerbera"
export APP_GERBERA_MEDIA_DIR="${EXPORTS_APP_DATA_DIR}/media"