#!/usr/bin/with-contenv bashio

export MYSQL_HOST="$(bashio::config 'mysql_host')"
export MYSQL_PORT="$(bashio::config 'mysql_port')"
export MYSQL_DATABASE="$(bashio::config 'mysql_database')"
export MYSQL_USER="$(bashio::config 'mysql_user')"
export MYSQL_PASSWORD="$(bashio::config 'mysql_password')"
export API_KEY="$(bashio::config 'api_key')"
export HA_BRIDGE_BASE_URL="$(bashio::config 'ha_bridge_base_url')"
export HA_PACKAGES_DIR_OPTION="$(bashio::config 'ha_packages_dir')"


# Generate Home Assistant bridge package.
if [ "${HA_PACKAGES_DIR_OPTION}" != "auto" ] && [ -n "${HA_PACKAGES_DIR_OPTION}" ]; then
  case "${HA_PACKAGES_DIR_OPTION}" in
    /*) HA_PACKAGES_DIR="/homeassistant${HA_PACKAGES_DIR_OPTION#/config}" ;;
    *)  HA_PACKAGES_DIR="/homeassistant/${HA_PACKAGES_DIR_OPTION}" ;;
  esac
elif [ -d /homeassistant/_packages ]; then
  HA_PACKAGES_DIR="/homeassistant/_packages"
elif [ -d /homeassistant/packages ]; then
  HA_PACKAGES_DIR="/homeassistant/packages"
else
  HA_PACKAGES_DIR="/homeassistant/_packages"
fi

mkdir -p "${HA_PACKAGES_DIR}"
BRIDGE_TARGET="${HA_PACKAGES_DIR}/life_manager_generated.yaml"

sed "s|__LIFE_MANAGER_BASE_URL__|${HA_BRIDGE_BASE_URL%/}|g" \
  /ha_bridge/life_manager_generated.yaml > "${BRIDGE_TARGET}" || {
    bashio::log.fatal "Konnte Home-Assistant-Bridge nicht schreiben."
    exit 1
  }

bashio::log.info "Home-Assistant-Bridge geschrieben: ${BRIDGE_TARGET}"
bashio::log.info "Bridge API URL: ${HA_BRIDGE_BASE_URL%/}"
bashio::log.info "Nach einer neuen/änderten Bridge ist ein Home Assistant Core Neustart erforderlich."

mkdir -p /homeassistant/www

FRONTEND_VERSION="1.6.5"
FRONTEND_FILE="life-manager-${FRONTEND_VERSION}.js"

cp /frontend/life-manager.js "/homeassistant/www/${FRONTEND_FILE}" || \
  bashio::log.fatal "Konnte Life Manager Frontend nicht nach /config/www kopieren."

cp /frontend/life-manager-loader.js /homeassistant/www/life-manager-loader.js || \
  bashio::log.fatal "Konnte Life Manager Loader nicht nach /config/www kopieren."

cat > /homeassistant/www/life-manager-manifest.json <<EOF
{"version":"${FRONTEND_VERSION}","file":"/local/${FRONTEND_FILE}"}
EOF

# Legacy filename deliberately stays updated too, so direct/manual access is not misleading.
cp /frontend/life-manager.js /homeassistant/www/life-manager.js || \
  bashio::log.warning "Konnte Legacy-Datei life-manager.js nicht aktualisieren."

bashio::log.info "Frontend ${FRONTEND_VERSION} und Loader nach /config/www aktualisiert."


bashio::log.info "Starte Life Manager API v0.7.2"

bashio::log.info "Prüfe Life Manager Datenbankmigrationen..."
cd /app

if ! python3 migrate.py; then
  bashio::log.fatal "Datenbankmigration fehlgeschlagen. API wird nicht gestartet."
  exit 1
fi

bashio::log.info "Starte Life Manager API v1.6.5"
exec uvicorn main:app --host 0.0.0.0 --port 8000
