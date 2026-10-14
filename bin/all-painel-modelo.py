#!/usr/bin/env python3
"""
ALL Tecnologias — cria o painel MODELO (um painel para todos os clientes) a partir do painel da Tecmar.

O que faz (só pela API do Metabase; nunca altera os bancos de dados dos sistemas):
  1. Lê o painel de origem (padrão: 19, "Painel do Cliente - Grupo Tecmar") e as perguntas dele.
  2. Cria a pasta "Modelo (teste)" e copia cada pergunta trocando os códigos da Tecmar pelos marcadores
     __ALL_ERP__, __ALL_TACTICAL__, __ALL_ZABBIX__, __ALL_BACULA__, __ALL_WAZUH__ e acrescenta a
     variável {{all_cliente}} (filtro "Cliente" da equipe).
  3. Cria o painel "Painel do Cliente (modelo)" com as mesmas abas, posições e o filtro "Cliente".
  4. (opcional, --configurar-grupo) cria o grupo "Grupo Tecmar", marca como grupo de cliente e grava os
     códigos dele em Admin → Grupos.

Precisa do fork com a filtragem por cliente (imagem portal-bi:teste ou mais nova) no Metabase de DESTINO.

Uso:
  export MB_URL=http://localhost:3001          # Metabase de destino (ex.: Metabase_Teste)
  export MB_KEY=mb_xxx                         # chave de API do destino (Admin → Configurações → Autenticação → Chaves de API)
  # origem diferente do destino (opcional; padrão = destino):
  export MB_SRC_URL=https://bi.alltecnologias.com.br MB_SRC_KEY=mb_yyy
  python3 bin/all-painel-modelo.py                       # mostra o plano e o relatório de troca, sem criar nada
  python3 bin/all-painel-modelo.py --aplicar             # cria pasta, perguntas e painel
  python3 bin/all-painel-modelo.py --aplicar --configurar-grupo
"""
import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
import uuid

CLIENT_TAG = "all_cliente"

TECMAR_CODES = {
    "erp": "6,7,23",
    "tactical": "Tecmar",
    "zabbix": "30",
    "bacula": "tecmar-pdceserver-fd",
    "wazuh": "cli_tecmar",
}
TECMAR_SERVICES = {"auditoria": True, "navegacao": False}

EMPRESA_SQL = (
    "(SELECT FIRST 1 CAST(COALESCE(NULLIF(TRIM(CE.FANTASIA_CLI), ''), TRIM(CE.NOME_CLI)) "
    "AS VARCHAR(60) CHARACTER SET WIN1252) FROM CADCLI CE WHERE CE.CODCLI = {expr})"
)

FIREWALL_HOSTS_SQL = (
    "h.hostid IN (SELECT fa.hostid FROM hosts_groups fa "
    "JOIN hosts_groups fb ON fb.hostid = fa.hostid AND fb.groupid = 25 "
    "WHERE fa.groupid = __ALL_ZABBIX__)"
)

# Perguntas cuja estrutura muda (o nome da empresa passa a vir do ERP).
OVERRIDES = {
    "Gasto por empresa": """SELECT {empresa} AS "Empresa",
       X.GASTO AS "Gasto (R$)"
FROM (
  SELECT O.CLIENTE_CLIOS AS CLI, CAST(SUM(COALESCE(O.VALORTOTAL_CLIOS, 0)) AS NUMERIC(12,2)) AS GASTO
  FROM CADCLI_OS O
  WHERE O.CLIENTE_CLIOS IN (__ALL_ERP__)
    AND COALESCE(O.APURACAO_CONTRATO_CLIOS, 'N') <> 'S'
    AND O.SITUACAO_CLIOS <> 0
    AND O.DATA_CLIOS >= DATEADD(-12 MONTH TO CURRENT_DATE)
  GROUP BY O.CLIENTE_CLIOS
) X
ORDER BY 2 DESC""".replace("{empresa}", EMPRESA_SQL.format(expr="X.CLI")),
}

RENAMES = {
    "Link 1 Giganet (7 dias)": "Link 1 (7 dias)",
    "Link 2 Uba Conect (7 dias)": "Link 2 (7 dias)",
}

CASE_EMPRESA = re.compile(
    r"CAST\(\s*(?:TRIM\(\s*)?CASE\s+(?P<expr>.+?)\s+WHEN\s+6\s+THEN\s+'Tecmar'.*?END\s*\)?\s*AS\s+VARCHAR\(\d+\)\s*\)",
    re.S,
)

RULES = [
    (re.compile(r"IN\s*\(\s*6\s*,\s*7\s*,\s*23\s*\)"), "IN (__ALL_ERP__)"),
    (re.compile(r"h\.host\s*=\s*'tecmar-utm'"), FIREWALL_HOSTS_SQL),
    (re.compile(r"groupid\s*=\s*30\b"), "groupid = __ALL_ZABBIX__"),
    (re.compile(r"'tecmar-pdceserver-fd'"), "'__ALL_BACULA__'"),
    (re.compile(r"\bcli_tecmar\."), "__ALL_WAZUH__."),
    (re.compile(r"=\s*'Tecmar'"), "= '__ALL_TACTICAL__'"),
]

LEFTOVER = re.compile(r"tecmar|protec|primicia|giganet|uba conect|6\s*,\s*7\s*,\s*23|groupid\s*=\s*30\b", re.I)


def convert_sql(name, sql):
    if name in OVERRIDES:
        out = OVERRIDES[name]
    else:
        out = CASE_EMPRESA.sub(lambda m: EMPRESA_SQL.format(expr=m.group("expr")), sql)
        for pattern, repl in RULES:
            out = pattern.sub(repl, out)
    out = out.rstrip().rstrip(";") + "\n/* {{" + CLIENT_TAG + "}} */"
    leftovers = sorted({m.group(0) for m in LEFTOVER.finditer(out)})
    return out, leftovers


class Api:
    def __init__(self, url, key):
        self.url = url.rstrip("/")
        self.key = key
        self.ctx = ssl.create_default_context()

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.url + path, data=data, method=method,
            headers={"x-api-key": self.key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=120) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            sys.exit(f"Erro {e.code} em {method} {path}: {e.read().decode(errors='replace')[:500]}")


def card_sql(card):
    dq = card.get("dataset_query") or {}
    if "stages" in dq:
        stage = dq["stages"][0]
        return stage.get("native"), dq.get("database")
    native = dq.get("native") or {}
    return native.get("query"), dq.get("database")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--configurar-grupo", action="store_true")
    ap.add_argument("--painel-origem", type=int, default=19)
    ap.add_argument("--grupo", default="Grupo Tecmar")
    ap.add_argument("--pasta", default="Modelo (teste)")
    ap.add_argument("--nome-painel", default="Painel do Cliente (modelo)")
    args = ap.parse_args()

    dst = Api(os.environ.get("MB_URL", ""), os.environ.get("MB_KEY", ""))
    if not dst.url or not dst.key:
        sys.exit("Defina MB_URL e MB_KEY (Metabase de destino).")
    src = Api(os.environ.get("MB_SRC_URL", dst.url), os.environ.get("MB_SRC_KEY", dst.key))

    dash = src.call("GET", f"/api/dashboard/{args.painel_origem}")
    print(f"Origem: {dash['name']} ({len(dash.get('tabs') or [])} abas, {len(dash['dashcards'])} cartões)")

    plan = []
    for dc in dash["dashcards"]:
        if not dc.get("card_id"):
            plan.append((dc, None, None, None))
            continue
        card = src.call("GET", f"/api/card/{dc['card_id']}")
        sql, db = card_sql(card)
        if sql is None:
            print(f"  ! {card['name']}: não é SQL, ficará de fora")
            continue
        new_sql, leftovers = convert_sql(card["name"], sql)
        plan.append((dc, card, (new_sql, db), leftovers))
        marks = sorted(set(re.findall(r"__ALL_[A-Z]+__", new_sql)))
        warn = f"  ATENÇÃO, sobrou: {leftovers}" if leftovers else ""
        print(f"  - {card['name']}: {', '.join(marks) or 'sem marcadores'}{warn}")

    if not args.aplicar:
        print("\nNada foi criado. Rode com --aplicar.")
        return

    coll = dst.call("POST", "/api/collection", {"name": args.pasta, "parent_id": None,
                                                "description": "Perguntas e painel modelo com marcadores __ALL_*__"})
    print(f"\nPasta criada: {coll['name']} (id {coll['id']})")

    param_id = uuid.uuid4().hex[:8]
    tab_ids = {t["id"]: -(i + 1) for i, t in enumerate(dash.get("tabs") or [])}
    new_cards = []
    for i, (dc, card, conv, _leftovers) in enumerate(plan):
        entry = {
            "id": -(i + 1),
            "row": dc["row"], "col": dc["col"], "size_x": dc["size_x"], "size_y": dc["size_y"],
            "dashboard_tab_id": tab_ids.get(dc.get("dashboard_tab_id")),
            "visualization_settings": dc.get("visualization_settings") or {},
            "parameter_mappings": [],
            "series": [],
        }
        if card is None:
            entry["card_id"] = None
            new_cards.append(entry)
            continue
        new_sql, db = conv
        name = RENAMES.get(card["name"], card["name"])
        created = dst.call("POST", "/api/card", {
            "name": name,
            "description": card.get("description"),
            "display": card["display"],
            "visualization_settings": card.get("visualization_settings") or {},
            "collection_id": coll["id"],
            "dataset_query": {
                "database": db,
                "type": "native",
                "native": {
                    "query": new_sql,
                    "template-tags": {CLIENT_TAG: {
                        "id": str(uuid.uuid4()), "name": CLIENT_TAG,
                        "display-name": "Cliente", "type": "text",
                        "default": args.grupo,
                    }},
                },
            },
        })
        print(f"  + pergunta {created['id']}: {name}")
        entry["card_id"] = created["id"]
        entry["parameter_mappings"] = [{
            "parameter_id": param_id, "card_id": created["id"],
            "target": ["variable", ["template-tag", CLIENT_TAG]],
        }]
        new_cards.append(entry)

    new_dash = dst.call("POST", "/api/dashboard", {
        "name": args.nome_painel, "collection_id": coll["id"],
        "description": "Painel único para todos os clientes (filtragem por cliente do fork ALL).",
    })
    dst.call("PUT", f"/api/dashboard/{new_dash['id']}", {
        "width": dash.get("width", "full"),
        "tabs": [{"id": tab_ids[t["id"]], "name": t["name"]} for t in (dash.get("tabs") or [])],
        "parameters": [{
            "id": param_id, "name": "Cliente", "slug": "cliente",
            "type": "string/=", "sectionId": "string",
            "default": [args.grupo],
            "values_query_type": "list",
            "values_source_type": "static-list",
            "values_source_config": {"values": [args.grupo]},
        }],
        "dashcards": new_cards,
    })
    print(f"Painel criado: {args.nome_painel} (id {new_dash['id']}) → {dst.url}/dashboard/{new_dash['id']}")

    if args.configurar_grupo:
        groups = dst.call("GET", "/api/permissions/group")
        group = next((g for g in groups if g["name"].strip().lower() == args.grupo.lower()), None)
        if group is None:
            group = dst.call("POST", "/api/permissions/group", {"name": args.grupo})
            print(f"Grupo criado: {args.grupo} (id {group['id']})")
        ids = dst.call("GET", "/api/setting/all-client-group-ids") or []
        if group["id"] not in ids:
            dst.call("PUT", "/api/setting/all-client-group-ids", {"value": ids + [group["id"]]})
        config = dst.call("GET", "/api/setting/all-client-group-config") or {}
        config[str(group["id"])] = {"codes": TECMAR_CODES, "services": TECMAR_SERVICES}
        dst.call("PUT", "/api/setting/all-client-group-config", {"value": config})
        print(f"Grupo {args.grupo} marcado como cliente e configurado: {TECMAR_CODES}")


if __name__ == "__main__":
    main()
