#!/usr/bin/with-contenv bashio

export MYSQL_HOST="$(bashio::config 'mysql_host')"
export MYSQL_PORT="$(bashio::config 'mysql_port')"
export MYSQL_DATABASE="$(bashio::config 'mysql_database')"
export MYSQL_USER="$(bashio::config 'mysql_user')"
export MYSQL_PASSWORD="$(bashio::config 'mysql_password')"
export API_KEY="$(bashio::config 'api_key')"

mkdir -p /homeassistant/www

FRONTEND_VERSION="1.4.0"
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

bashio::log.info "Starte Life Manager API v1.4.0"
exec uvicorn main:app --host 0.0.0.0 --port 8000
