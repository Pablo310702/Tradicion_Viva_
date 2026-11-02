#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/opc/tradicion-viva}"
BACKUP_DIR="${BACKUP_DIR:-/home/opc/backups/tradicion-viva}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.production.yml"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FINAL_PATH="$BACKUP_DIR/tradicion_viva_${STAMP}.dump"
TEMP_PATH="${FINAL_PATH}.tmp"

mkdir -p "$BACKUP_DIR"
trap 'rm -f "$TEMP_PATH"' EXIT

cd "$PROJECT_DIR"
docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U tradicion_viva -d tradicion_viva -Fc > "$TEMP_PATH"

# Verifica que el archivo sea legible antes de publicarlo como backup válido.
docker run --rm -v "$TEMP_PATH:/backup.dump:ro" postgres:16-alpine \
  pg_restore --list /backup.dump >/dev/null

mv "$TEMP_PATH" "$FINAL_PATH"
chmod 600 "$FINAL_PATH"
find "$BACKUP_DIR" -type f -name 'tradicion_viva_*.dump' \
  -mtime "+$RETENTION_DAYS" -delete

echo "Backup verificado: $FINAL_PATH"
