#!/bin/sh
# Backup do PostgreSQL + anexos.
#   sh backup.sh agora      -> um backup imediato
#   sh backup.sh agendado   -> laço diário na hora BACKUP_HORA (padrão 02h)
# O administrador deve copiar a pasta de backups para fora do servidor (exigência da especificação).
set -eu
DESTINO=/backups
RETENCAO=${BACKUP_RETENCAO_DIAS:-30}

fazer_backup() {
  carimbo=$(date +%Y-%m-%d_%H%M)
  mkdir -p "$DESTINO"
  pg_dump -Fc -f "$DESTINO/banco_$carimbo.dump"
  tar -czf "$DESTINO/anexos_$carimbo.tar.gz" -C /dados anexos 2>/dev/null || true
  # valida que o dump é legível (restauração testável)
  pg_restore -l "$DESTINO/banco_$carimbo.dump" > /dev/null
  find "$DESTINO" -name 'banco_*.dump' -mtime +"$RETENCAO" -delete
  find "$DESTINO" -name 'anexos_*.tar.gz' -mtime +"$RETENCAO" -delete
  echo "$(date) backup concluído: banco_$carimbo.dump"
}

if [ "${1:-agora}" = "agendado" ]; then
  echo "Backup agendado diariamente às ${BACKUP_HORA:-02}h, retenção de $RETENCAO dias."
  ultimo=""
  while true; do
    hoje=$(date +%Y-%m-%d)
    if [ "$(date +%H)" = "${BACKUP_HORA:-02}" ] && [ "$ultimo" != "$hoje" ]; then
      fazer_backup && ultimo=$hoje
    fi
    sleep 300
  done
else
  fazer_backup
fi
