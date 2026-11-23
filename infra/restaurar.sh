#!/bin/sh
# Restaura um backup. Uso (na pasta do projeto):
#   sh infra/restaurar.sh backups/banco_2026-11-23_0200.dump [backups/anexos_2026-11-23_0200.tar.gz]
# ATENÇÃO: substitui os dados atuais. Pare api e worker antes: docker compose stop api worker
set -eu
DUMP=${1:?informe o arquivo .dump}
docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$DUMP"
if [ -n "${2:-}" ]; then
  docker compose run --rm -T -v "$(pwd)/$(dirname "$2"):/b:ro" --entrypoint sh api -c "tar -xzf /b/$(basename "$2") -C /dados"
fi
echo "Restauração concluída. Suba novamente: docker compose up -d"
