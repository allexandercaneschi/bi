#!/usr/bin/env bash
# ALL Tecnologias — copia o Metabase de PRODUÇÃO para o Metabase_Teste.
#
# Hoje o Metabase_Teste usa um banco H2 dentro do volume metabase-all-teste. Este script:
#   1. cria um PostgreSQL só do teste (container Metabase_Teste_DB, volume metabase-teste-pg);
#   2. copia o banco de aplicação da produção para ele (pg_dump só LÊ a produção; ela continua no ar);
#   3. recria o Metabase_Teste apontando para esse banco, na mesma porta 3002, com a pasta de drivers
#      /root/metabase-plugins (Firebird do ERP) e com o agendador DESLIGADO (não manda e-mail de assinatura).
#
# O container antigo fica guardado como Metabase_Teste_H2 (parado) para voltar atrás, se precisar.
# Os bancos dos sistemas (Zabbix, ERP, Tactical, Bacula, Wazuh) não são tocados.
#
# Uso (no servidor Docker, como root):  bash all-copiar-producao-para-teste.sh
# Rodar de novo atualiza a cópia (apaga o conteúdo do banco do teste e copia a produção outra vez).
set -euo pipefail

PROD="${PROD:-Metabase_Producao}"
TESTE="${TESTE:-Metabase_Teste}"
DB="${TESTE}_DB"
NET="metabase-teste-net"
IMAGE_TESTE="${IMAGE_TESTE:-ghcr.io/allexandercaneschi/portal-bi:teste}"
PORTA="${PORTA:-3002}"
ENVF=/root/metabase-teste.env

prod_env() { docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$PROD" | sed -n "s/^$1=//p"; }

P_HOST="$(prod_env MB_DB_HOST)"; P_PORT="$(prod_env MB_DB_PORT)"; P_PORT="${P_PORT:-5432}"
P_DB="$(prod_env MB_DB_DBNAME)"; P_USER="$(prod_env MB_DB_USER)"; P_PASS="$(prod_env MB_DB_PASS)"
[ -n "$P_HOST" ] || { echo "Não achei MB_DB_HOST no container $PROD."; exit 1; }

if [ ! -f "$ENVF" ]; then
  umask 077
  echo "TPASS=$(openssl rand -hex 16)" > "$ENVF"
fi
# shellcheck disable=SC1090
. "$ENVF"

docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET" >/dev/null

if ! docker inspect "$DB" >/dev/null 2>&1; then
  echo "[1/4] Criando o PostgreSQL do teste ($DB)"
  docker run -d --name "$DB" --restart unless-stopped --network "$NET" \
    -e POSTGRES_USER=metabase -e POSTGRES_PASSWORD="$TPASS" -e POSTGRES_DB=metabase \
    -v metabase-teste-pg:/var/lib/postgresql postgres:18 >/dev/null
else
  echo "[1/4] PostgreSQL do teste já existe ($DB)"
fi
for _ in $(seq 1 30); do docker exec "$DB" pg_isready -U metabase >/dev/null 2>&1 && break; sleep 2; done

echo "[2/4] Copiando a produção ($P_HOST:$P_PORT/$P_DB) — só leitura"
docker exec -e PGPASSWORD="$P_PASS" "$DB" pg_dump -h "$P_HOST" -p "$P_PORT" -U "$P_USER" -d "$P_DB" -Fc -f /tmp/producao.dump

echo "[3/4] Restaurando no banco do teste"
if docker inspect "$TESTE" >/dev/null 2>&1; then docker stop "$TESTE" >/dev/null; fi
docker exec "$DB" pg_restore -U metabase -d metabase --clean --if-exists --no-owner --no-privileges /tmp/producao.dump
docker exec "$DB" rm -f /tmp/producao.dump
CARDS=$(docker exec "$DB" psql -U metabase -d metabase -tAc 'select count(*) from report_card where not archived')
DASHS=$(docker exec "$DB" psql -U metabase -d metabase -tAc 'select count(*) from report_dashboard where not archived')
echo "      $CARDS perguntas e $DASHS painéis copiados"

echo "[4/4] Recriando o $TESTE no PostgreSQL (porta $PORTA)"
if docker inspect "$TESTE" >/dev/null 2>&1; then
  if [ "$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$TESTE" | grep -c '^MB_DB_HOST=')" = "0" ]; then
    docker rm -f "${TESTE}_H2" >/dev/null 2>&1 || true
    docker rename "$TESTE" "${TESTE}_H2"
    echo "      container antigo (H2) guardado como ${TESTE}_H2 (parado)"
  else
    docker rm -f "$TESTE" >/dev/null
  fi
fi
docker pull -q "$IMAGE_TESTE" >/dev/null
docker run -d --name "$TESTE" --restart unless-stopped --network "$NET" -p "$PORTA:3000" \
  -v /root/metabase-plugins:/plugins \
  -e MB_DB_TYPE=postgres -e MB_DB_HOST="$DB" -e MB_DB_PORT=5432 \
  -e MB_DB_DBNAME=metabase -e MB_DB_USER=metabase -e MB_DB_PASS="$TPASS" \
  -e MB_DISABLE_SCHEDULER=true \
  "$IMAGE_TESTE" >/dev/null

echo
echo "Pronto. O Metabase_Teste sobe em 1 a 3 minutos na porta $PORTA."
echo "Mesmos usuários e senhas da produção. Confira em Admin → Configurações → Geral a 'URL do site'."
echo "Acompanhar: docker logs -f $TESTE"
