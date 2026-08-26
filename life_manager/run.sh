#!/usr/bin/with-contenv bashio

export MYSQL_HOST="$(bashio::config 'mysql_host')"
export MYSQL_PORT="$(bashio::config 'mysql_port')"
export MYSQL_DATABASE="$(bashio::config 'mysql_database')"
export MYSQL_USER="$(bashio::config 'mysql_user')"
export MYSQL_PASSWORD="$(bashio::config 'mysql_password')"
export API_KEY="$(bashio::config 'api_key')"

mkdir -p /homeassistant/www
cp /frontend/life-manager.js /homeassistant/www/life-manager.js || \
  bashio::log.warning "Konnte life-manager.js nicht automatisch nach /config/www kopieren."

bashio::log.info "Starte Life Manager API v0.7.2"

bashio::log.info "Prüfe Life Manager Datenbankmigrationen..."
cd /app

if ! python3 migrate.py; then
  bashio::log.fatal "Datenbankmigration fehlgeschlagen. API wird nicht gestartet."
  exit 1
fi

bashio::log.info "Starte Life Manager API v0.9.1"
exec uvicorn main:app --host 0.0.0.0 --port 8000
