#!/usr/bin/env bash
# ALL Tecnologias — copia o banco de aplicação do Metabase de PRODUÇÃO para o Metabase_Teste.
#
# Copia perguntas, painéis, pastas, usuários, grupos, conexões com os bancos (Zabbix, ERP, Tactical...)
# e configurações. Os bancos dos sistemas NÃO são tocados: o teste passa a ler os mesmos bancos, só leitura.
#
# - Só lê a produção (pg_dump). A produção continua no ar.
# - Antes de sobrescrever, faz backup do banco do teste em /root/copia-metabase-<data>/teste-antes.dump
# - Recusa rodar se os dois containers apontarem para o MESMO banco.
#
# Uso (no servidor Docker, como root):
#   bash all-copiar-producao-para-teste.sh                 # usa os containers "Metabase" e "Metabase_Teste"
#   PROD=Metabase TESTE=Metabase_Teste bash all-copiar-producao-para-teste.sh
set -euo pipefail

PROD="${PROD:-Metabase}"
TESTE="${TESTE:-Metabase_Teste}"
PG_IMAGE="${PG_IMAGE:-postgres:18}"

load_env() { # $1 = prefixo, $2 = container
  local line key val
  while IFS= read -r line; do
    key="${line%%=*}"; val="${line#*=}"
    case "$key" in MB_DB_*) printf -v "${1}_${key}" '%s' "$val" ;; esac
  done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$2")
}

network_of() {
  docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' "$1" | head -n1
}

load_env P "$PROD"
load_env T "$TESTE"

for p in P T; do
  host_var="${p}_MB_DB_HOST"
  if [ -z "${!host_var:-}" ]; then
    echo "O container $([ $p = P ] && echo "$PROD" || echo "$TESTE") não tem MB_DB_HOST (usa H2?). Este script só copia PostgreSQL."
    exit 1
  fi
done

P_PORT="${P_MB_DB_PORT:-5432}"; T_PORT="${T_MB_DB_PORT:-5432}"
P_ID="${P_MB_DB_HOST}:${P_PORT}/${P_MB_DB_DBNAME}"
T_ID="${T_MB_DB_HOST}:${T_PORT}/${T_MB_DB_DBNAME}"
echo "Produção: $PROD → $P_ID"
echo "Teste:    $TESTE → $T_ID"
if [ "$P_ID" = "$T_ID" ]; then
  echo "Os dois apontam para o MESMO banco. Nada foi feito."
  exit 1
fi

P_NET="$(network_of "$PROD")"; T_NET="$(network_of "$TESTE")"
DIR="/root/copia-metabase-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DIR"

pg() { # $1 = rede, $2 = senha, resto = comando
  local net="$1" pass="$2"; shift 2
  docker run --rm --network "$net" -e PGPASSWORD="$pass" -v "$DIR:/bk" "$PG_IMAGE" "$@"
}

echo "1/4 Backup do banco do teste → $DIR/teste-antes.dump"
pg "$T_NET" "$T_MB_DB_PASS" pg_dump -h "$T_MB_DB_HOST" -p "$T_PORT" -U "$T_MB_DB_USER" -d "$T_MB_DB_DBNAME" -Fc -f /bk/teste-antes.dump

echo "2/4 Copiando a produção (só leitura) → $DIR/producao.dump"
pg "$P_NET" "$P_MB_DB_PASS" pg_dump -h "$P_MB_DB_HOST" -p "$P_PORT" -U "$P_MB_DB_USER" -d "$P_MB_DB_DBNAME" -Fc -f /bk/producao.dump

echo "3/4 Parando o $TESTE e restaurando a cópia no banco do teste"
docker stop "$TESTE" >/dev/null
pg "$T_NET" "$T_MB_DB_PASS" pg_restore -h "$T_MB_DB_HOST" -p "$T_PORT" -U "$T_MB_DB_USER" -d "$T_MB_DB_DBNAME" \
  --clean --if-exists --no-owner --no-privileges --single-transaction /bk/producao.dump

echo "4/4 Subindo o $TESTE"
docker start "$TESTE" >/dev/null

cat <<EOF

Pronto. Aguarde 1 a 2 minutos o Metabase_Teste iniciar.
Depois, no teste:
  - Admin → Configurações → Geral: confira a "URL do site" (veio a da produção).
  - Para desfazer: pg_restore do arquivo $DIR/teste-antes.dump do mesmo jeito.
EOF
