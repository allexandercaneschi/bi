#!/usr/bin/env python3
"""
ALL Tecnologias — filtros por aba do painel modelo, versão 2 (todos em lista, datas com calendário).

Regera o SQL de cada pergunta do painel modelo a partir das perguntas de origem (painel da Tecmar e painel de
Auditoria), troca os códigos pelos marcadores __ALL_*__ (bin/all-painel-modelo.py) e acrescenta os filtros:

  Resumo ............ Empresa*
  Estações .......... Dispositivo, Usuário
  Atendimentos ...... Data inicial, Data final, Dispositivo, Empresa*
  Manutenções ....... Data inicial, Data final, Dispositivo, Empresa*
  Backup ............ Data inicial, Data final, Servidor, Job
  Auditoria ......... Servidor, Usuário, Ação, Severidade, Arquivo, Data inicial, Data final
  Navegação ......... Data inicial, Data final, Dispositivo, Usuário
  (* Empresa só aparece para clientes com mais de uma empresa no ERP — regra do fork)

Sem data escolhida, cada pergunta usa a janela padrão dela (12 meses, 30 dias, 7 dias...).
As listas dos filtros vêm de perguntas "Lista · ..." com marcadores: cada cliente vê só os itens dele.

Uso (na pasta onde estão também all-painel-modelo.py e all-navegacao-demo.py):
  export MB_URL=http://localhost:3002 MB_KEY=mb_...
  python3 all-filtros-abas-v2.py            # relatório
  python3 all-filtros-abas-v2.py --aplicar
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


modelo = load("modelo", "all-painel-modelo.py")
nav = load("nav", "all-navegacao-demo.py")

# pergunta do painel modelo → pergunta de origem (ids iguais na produção e na cópia de teste)
SOURCE = {243: 200, 244: 204, 245: 212, 246: 218, 247: 207, 248: 214, 249: 215, 250: 210, 251: 217, 252: 209,
          253: 202, 254: 199, 255: 198, 256: 201, 257: 219, 258: 216, 259: 203, 260: 213, 261: 211, 280: 238,
          269: 90, 270: 87, 271: 89, 272: 92, 273: 93, 274: 85, 275: 88, 276: 94, 277: 86, 278: 91}
NAV_CARDS = {281 + i: c for i, c in enumerate(nav.CARDS)}

TABS = [("resumo", r"resumo"), ("estacoes", r"esta[cç]"), ("atendimentos", r"atendiment"),
        ("manutencoes", r"manuten"), ("backup", r"backup"), ("auditoria", r"auditoria"),
        ("navegacao", r"navega")]

LABELS = {"data_inicial": "Data inicial", "data_final": "Data final", "dispositivo": "Dispositivo",
          "usuario": "Usuário", "empresa": "Empresa", "servidor": "Servidor", "job": "Job",
          "acao": "Ação", "severidade": "Severidade", "arquivo": "Arquivo"}

# ---------------------------------------------------------------- ERP (Firebird)
DI = "{{data_inicial}}"
DF = "{{data_final}}"


def fb_periodo(col, default):
    return (f"{col} >= COALESCE(NULL [[, CAST({DI} AS DATE)]], {default}) "
            f"AND {col} < COALESCE(NULL [[, DATEADD(1 DAY TO CAST({DF} AS DATE))]], DATEADD(1 DAY TO CURRENT_DATE))")


EMPRESA_IN = ("(SELECT CE9.CODCLI FROM CADCLI CE9 WHERE "
              "COALESCE(NULLIF(TRIM(CE9.FANTASIA_CLI), ''), TRIM(CE9.NOME_CLI)) = {{empresa}})")
ATD_EMP = ("[[AND COALESCE((SELECT FIRST 1 SE9.CLIENTE_ASTAG FROM SERVICE_TAG SE9 WHERE SE9.SERVICE_TAG_ASTAG = A.SERVICE_TAG_ATD), "
           "A.CLIENTE_ATD) IN " + EMPRESA_IN + "]]")
OS_EMP = ("[[AND COALESCE((SELECT FIRST 1 SE9.CLIENTE_ASTAG FROM CADCLI_OS_EQUIPAM EE9 JOIN SERVICE_TAG SE9 "
          "ON SE9.SERVICE_TAG_ASTAG = EE9.SERVICE_TAG_COEQ WHERE EE9.OS_COEQ = O.CODIGO_CLIOS AND EE9.EMPRESA_COEQ = O.EMPRESA_CLIOS), "
          "O.CLIENTE_CLIOS) IN " + EMPRESA_IN + "]]")
ST_EMP = "[[AND S.CLIENTE_ASTAG IN " + EMPRESA_IN + "]]"
ATD_DISP = ("[[AND A.SERVICE_TAG_ATD IN (SELECT SD9.SERVICE_TAG_ASTAG FROM SERVICE_TAG SD9 "
            "WHERE TRIM(SD9.DESCRICAO_ASTAG) = {{dispositivo}})]]")
OS_DISP = ("[[AND EXISTS (SELECT 1 FROM CADCLI_OS_EQUIPAM ED9 JOIN SERVICE_TAG SD9 ON SD9.SERVICE_TAG_ASTAG = ED9.SERVICE_TAG_COEQ "
           "WHERE ED9.OS_COEQ = O.CODIGO_CLIOS AND ED9.EMPRESA_COEQ = O.EMPRESA_CLIOS AND TRIM(SD9.DESCRICAO_ASTAG) = {{dispositivo}})]]")


def erp_filters(sql, tab):
    out = sql
    if tab in ("atendimentos", "manutencoes"):
        out = re.sub(r"\b([AO]\.(?:DATAINICIO_ATD|DATA_CLIOS))\s*>=\s*DATEADD\(-12 MONTH TO CURRENT_DATE\)",
                     lambda m: fb_periodo(m.group(1), "DATEADD(-12 MONTH TO CURRENT_DATE)"), out)
        if "{{data_inicial}}" not in out and "O.CLIENTE_CLIOS IN (__ALL_ERP__)" in out:
            # sem janela (ex.: custo por dispositivo): sem data = todo o histórico
            out = out.replace("O.CLIENTE_CLIOS IN (__ALL_ERP__)",
                              "O.CLIENTE_CLIOS IN (__ALL_ERP__) AND " + fb_periodo("O.DATA_CLIOS", "DATE '1900-01-01'"), 1)
    extra_a, extra_o = "", ""
    if tab in ("atendimentos", "manutencoes"):
        extra_a += " " + ATD_DISP
        extra_o += " " + OS_DISP
    if tab in ("resumo", "atendimentos", "manutencoes"):
        extra_a += " " + ATD_EMP
        extra_o += " " + OS_EMP
        out = out.replace("S.CLIENTE_ASTAG IN (__ALL_ERP__)", "S.CLIENTE_ASTAG IN (__ALL_ERP__) " + ST_EMP, 1)
    if extra_a:
        out = out.replace("A.CLIENTE_ATD IN (__ALL_ERP__)", "A.CLIENTE_ATD IN (__ALL_ERP__)" + extra_a, 1)
    if extra_o:
        out = out.replace("O.CLIENTE_CLIOS IN (__ALL_ERP__)", "O.CLIENTE_CLIOS IN (__ALL_ERP__)" + extra_o, 1)
    return out


# ---------------------------------------------------------------- Postgres
def pg_periodo(col, default, now="now()", cast="timestamp"):
    return (f"{col} >= COALESCE(NULL [[, {DI}::date::{cast}]], {default}) "
            f"AND {col} < COALESCE(NULL [[, ({DF}::date + 1)::{cast}]], {now} + interval '1 day')")


def bacula_filters(sql, name):
    out = sql
    out = re.sub(r"\bj\.starttime\s*>=\s*now\(\)\s*-\s*interval\s*'30 days'",
                 lambda m: pg_periodo("j.starttime", "now() - interval '30 days'"), out)
    out = out.replace("c.clientid IN (__ALL_BACULA__)",
                      "c.clientid IN (__ALL_BACULA__) [[AND c.name = {{servidor}}]] [[AND j.name = {{job}}]]", 1)
    return out


def tactical_filters(sql):
    return sql.replace("c.name = '__ALL_TACTICAL__'",
                       "c.name = '__ALL_TACTICAL__' [[AND a.hostname = {{dispositivo}}]] "
                       "[[AND (a.logged_in_username = {{usuario}} OR a.last_logged_in_user = {{usuario}})]]", 1)


NAV_NOW = "(now() AT TIME ZONE 'America/Sao_Paulo')"


def nav_sql(card):
    base = nav.BASE.replace("% 7) * interval '1 day')", "% 90) * interval '1 day')")
    base = base.replace("generate_series(1, 2000 + abs(hashtext((SELECT cli FROM p))) % 1500)",
                        "generate_series(1, (2000 + abs(hashtext((SELECT cli FROM p))) % 1500) * 13)")
    base = base.replace("WHERE a.data_hora <= now() AT TIME ZONE 'America/Sao_Paulo'",
                        f"WHERE a.data_hora <= {NAV_NOW} AND "
                        + pg_periodo("a.data_hora", f"{NAV_NOW} - interval '7 days'", now=NAV_NOW)
                        + " [[AND u.estacao = {{dispositivo}}]] [[AND u.usuario = {{usuario}}]]")
    return base + card["sql"]


# ---------------------------------------------------------------- listas dos filtros
def lists(dbs):
    erp, tac, bac, wz = dbs["erp"], dbs["tactical"], dbs["bacula"], dbs["wazuh"]
    tac_from = ("FROM agents_agent a JOIN clients_site s ON s.id = a.site_id "
                "JOIN clients_client c ON c.id = s.client_id WHERE c.name = '__ALL_TACTICAL__'")
    nav_base = nav_sql({"sql": ""}).split("\nn AS (")[0].rstrip().rstrip(",")
    return {
        "empresa": (erp, "Empresa",
                    "SELECT CAST(COALESCE(NULLIF(TRIM(C.FANTASIA_CLI), ''), TRIM(C.NOME_CLI)) AS VARCHAR(60) CHARACTER SET WIN1252) "
                    "AS \"Empresa\" FROM CADCLI C WHERE C.CODCLI IN (__ALL_ERP__) ORDER BY 1"),
        "disp_erp": (erp, "Dispositivo",
                     "SELECT DISTINCT CAST(TRIM(S.DESCRICAO_ASTAG) AS VARCHAR(100) CHARACTER SET WIN1252) AS \"Dispositivo\" "
                     "FROM SERVICE_TAG S WHERE S.CLIENTE_ASTAG IN (__ALL_ERP__) AND TRIM(S.DESCRICAO_ASTAG) <> '' ORDER BY 1"),
        "disp_estacoes": (tac, "Dispositivo", f"SELECT DISTINCT a.hostname AS \"Dispositivo\" {tac_from} ORDER BY 1"),
        "usu_estacoes": (tac, "Usuário",
                         f"SELECT x.u AS \"Usuário\" FROM (SELECT a.logged_in_username AS u {tac_from} "
                         f"UNION SELECT a.last_logged_in_user {tac_from}) x "
                         "WHERE x.u IS NOT NULL AND x.u NOT IN ('', 'None') ORDER BY 1"),
        "srv_backup": (bac, "Servidor", "SELECT c.name AS \"Servidor\" FROM client c WHERE c.clientid IN (__ALL_BACULA__) ORDER BY 1"),
        "job_backup": (bac, "Job", "SELECT DISTINCT j.name AS \"Job\" FROM job j WHERE j.clientid IN (__ALL_BACULA__) "
                                   "AND j.type = 'B' ORDER BY 1"),
        "srv_aud": (wz, "Servidor", "SELECT e.servidor AS \"Servidor\" FROM __ALL_WAZUH__.eventos_arquivos e "
                                    "WHERE e.data_hora >= now() - interval '90 days' GROUP BY 1 ORDER BY 1"),
        "usu_aud": (wz, "Usuário", "SELECT e.usuario AS \"Usuário\" FROM __ALL_WAZUH__.eventos_arquivos e "
                                   "WHERE e.data_hora >= now() - interval '90 days' GROUP BY 1 ORDER BY 1"),
        "acao_aud": (wz, "Ação", "SELECT e.acao AS \"Ação\" FROM __ALL_WAZUH__.eventos_arquivos e "
                                 "WHERE e.data_hora >= now() - interval '90 days' GROUP BY 1 ORDER BY 1"),
        "arq_aud": (wz, "Arquivo", "SELECT x.arquivo AS \"Arquivo\" FROM (SELECT e.arquivo, max(e.data_hora) AS ult "
                                   "FROM __ALL_WAZUH__.eventos_arquivos e WHERE e.data_hora >= now() - interval '90 days' "
                                   "AND e.arquivo IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 1000) x ORDER BY 1"),
        "disp_nav": (wz, "Dispositivo", nav_base + "\nSELECT DISTINCT u.estacao AS \"Dispositivo\" FROM u ORDER BY 1"),
        "usu_nav": (wz, "Usuário", nav_base + "\nSELECT DISTINCT u.usuario AS \"Usuário\" FROM u ORDER BY 1"),
    }


# parâmetros do painel: slug → (nome, aba(s), tag, lista)
PARAMS = [
    ("empresa", "Empresa", ("resumo", "atendimentos", "manutencoes"), "empresa", "empresa"),
    ("data_inicial", "Data inicial", ("atendimentos", "manutencoes", "backup", "auditoria", "navegacao"), "data_inicial", None),
    ("data_final", "Data final", ("atendimentos", "manutencoes", "backup", "auditoria", "navegacao"), "data_final", None),
    ("disp_erp", "Dispositivo", ("atendimentos", "manutencoes"), "dispositivo", "disp_erp"),
    ("disp_estacoes", "Dispositivo", ("estacoes",), "dispositivo", "disp_estacoes"),
    ("usu_estacoes", "Usuário", ("estacoes",), "usuario", "usu_estacoes"),
    ("srv_backup", "Servidor", ("backup",), "servidor", "srv_backup"),
    ("job_backup", "Job", ("backup",), "job", "job_backup"),
    ("srv_aud", "Servidor", ("auditoria",), "servidor", "srv_aud"),
    ("usu_aud", "Usuário", ("auditoria",), "usuario", "usu_aud"),
    ("acao_aud", "Ação", ("auditoria",), "acao", "acao_aud"),
    ("sev_aud", "Severidade", ("auditoria",), "severidade", "static:Crítica,Alta,Média,Baixa"),
    ("arq_aud", "Arquivo", ("auditoria",), "arquivo", "arq_aud"),
    ("disp_nav", "Dispositivo", ("navegacao",), "dispositivo", "disp_nav"),
    ("usu_nav", "Usuário", ("navegacao",), "usuario", "usu_nav"),
]


class Api:
    def __init__(self, url, key):
        self.url, self.key = url.rstrip("/"), key

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method,
                                     headers={"x-api-key": self.key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            sys.exit(f"Erro {e.code} em {method} {path}: {e.read().decode(errors='replace')[:500]}")


def card_sql(card):
    dq = card["dataset_query"]
    return dq["native"]["query"] if "native" in dq else dq["stages"][0]["native"]


def tags_for(sql, cliente_default):
    tags, params = {}, []
    for name in sorted(set(re.findall(r"\{\{\s*(\w+)\s*\}\}", sql))):
        t = {"id": f"all-{name}", "name": name, "type": "text",
             "display-name": "Cliente" if name == "all_cliente" else LABELS.get(name, name)}
        if name == "all_cliente" and cliente_default:
            t["default"] = cliente_default
        tags[name] = t
        params.append({"id": t["id"], "type": "category", "name": t["display-name"], "slug": name,
                       "target": ["variable", ["template-tag", name]],
                       **({"default": t["default"]} if t.get("default") else {})})
    return tags, params


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--painel", type=int, default=20)
    args = ap.parse_args()
    api = Api(os.environ.get("MB_URL", ""), os.environ.get("MB_KEY", ""))
    if not api.url or not api.key:
        sys.exit("Defina MB_URL e MB_KEY.")

    dash = api.call("GET", f"/api/dashboard/{args.painel}")
    tabs = {t["id"]: next((k for k, rx in TABS if re.search(rx, t["name"], re.I)), None) for t in dash["tabs"]}
    cliente = next(p for p in dash["parameters"] if p["slug"] == "cliente")
    cliente_default = (cliente.get("default") or [None])[0]
    coll = None

    plan = {}
    for dc in dash["dashcards"]:
        card = dc.get("card") or {}
        cid = card.get("id")
        if not cid:
            continue
        coll = coll or card.get("collection_id")
        tab = tabs.get(dc.get("dashboard_tab_id"))
        if cid in NAV_CARDS:
            new = nav_sql(NAV_CARDS[cid])
        elif cid in SOURCE:
            src = api.call("GET", f"/api/card/{SOURCE[cid]}")
            new, left = modelo.convert_sql(src["name"], card_sql(src))
            new = new.replace("\n/* {{all_cliente}} */", "")
            if left:
                print(f"  ! {card['name']}: sobrou {left}")
            if tab in ("resumo", "atendimentos", "manutencoes"):
                new = erp_filters(new, tab)
            if tab == "backup" and "__ALL_BACULA__" in new:
                new = bacula_filters(new, card["name"])
            if tab == "estacoes":
                new = tactical_filters(new)
        else:
            continue
        new += "\n/* {{all_cliente}} */"
        used = sorted(set(re.findall(r"\{\{\s*(\w+)\s*\}\}", new)) - {"all_cliente"})
        plan[cid] = (dc, tab, card, new, used)
        print(f"  - [{tab}] {card['name']}: {', '.join(used) or '-'}")

    if not args.aplicar:
        print("\nNada foi alterado. Rode com --aplicar.")
        return

    dbs = {"erp": api.call("GET", "/api/card/201")["database_id"], "tactical": api.call("GET", "/api/card/198")["database_id"],
           "bacula": api.call("GET", "/api/card/200")["database_id"], "wazuh": api.call("GET", "/api/card/85")["database_id"]}

    # arquiva listas antigas criadas por versões anteriores
    for item in api.call("GET", f"/api/collection/{coll}/items?models=card")["data"]:
        if item["name"].startswith("Lista · ") or item["name"] == "Empresas do cliente":
            api.call("PUT", f"/api/card/{item['id']}", {"archived": True})

    list_cards = {}
    for key, (db, col, sql) in lists(dbs).items():
        sql = sql + "\n/* {{all_cliente}} */"
        tags, cparams = tags_for(sql, cliente_default)
        c = api.call("POST", "/api/card", {
            "name": f"Lista · {LABELS.get(col.lower(), col)} ({key})", "display": "table", "collection_id": coll,
            "description": "Fonte de um filtro em lista do painel modelo.", "visualization_settings": {},
            "parameters": cparams,
            "dataset_query": {"database": db, "type": "native", "native": {"query": sql, "template-tags": tags}}})
        list_cards[key] = (c["id"], col)
    print(f"  + {len(list_cards)} listas de filtro criadas")

    params = [cliente]
    by_slug = {}
    for slug, name, _tabs, _tag, source in PARAMS:
        p = {"id": f"all_{slug}", "name": name, "slug": slug}
        if slug.startswith("data_"):
            p.update({"type": "date/single", "sectionId": "date"})
        else:
            p.update({"type": "string/=", "sectionId": "string", "values_query_type": "list",
                      "filteringParameters": [cliente["id"]]})
            if source.startswith("static:"):
                p.update({"values_source_type": "static-list",
                          "values_source_config": {"values": source[7:].split(",")}})
            else:
                cid, col = list_cards[source]
                p.update({"values_source_type": "card",
                          "values_source_config": {"card_id": cid, "value_field": ["field", col, {"base-type": "type/Text"}]}})
        params.append(p)
        by_slug[slug] = p

    for cid, (dc, tab, card, new, used) in plan.items():
        tags, cparams = tags_for(new, cliente_default)
        name = re.sub(r"\s*\((7|30) dias\)$|\s*\(12 meses\)$", "", card["name"])
        api.call("PUT", f"/api/card/{cid}", {
            "name": name, "parameters": cparams,
            "dataset_query": {"database": card["database_id"], "type": "native",
                              "native": {"query": new, "template-tags": tags}}})
        maps = [m for m in dc.get("parameter_mappings") or [] if m["parameter_id"] == cliente["id"]]
        for slug, _name, ptabs, tag, _src in PARAMS:
            if tab in ptabs and tag in used:
                maps.append({"parameter_id": by_slug[slug]["id"], "card_id": cid,
                             "target": ["variable", ["template-tag", tag]]})
        dc["parameter_mappings"] = maps

    keep = [{k: dc.get(k) for k in ("id", "card_id", "dashboard_tab_id", "row", "col", "size_x", "size_y",
                                    "parameter_mappings", "visualization_settings", "series")}
            for dc in dash["dashcards"]]
    api.call("PUT", f"/api/dashboard/{args.painel}", {
        "parameters": params, "tabs": [{"id": t["id"], "name": t["name"]} for t in dash["tabs"]], "dashcards": keep})
    print("Filtros:", ", ".join(f"{p['name']} ({p['slug']})" for p in params))


if __name__ == "__main__":
    main()
