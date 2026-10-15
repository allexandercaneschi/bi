#!/usr/bin/env python3
"""
ALL Tecnologias — filtros por aba no painel modelo (Período, Dispositivo e Empresa).

- Período: um filtro por aba (cada aba tem seu padrão), com opções fáceis para o gestor
  (Últimos 7/30/90 dias, 12 meses, Este mês, Mês passado, Este ano, Todo o período).
- Dispositivo: caixa de texto ("contém"), compartilhada entre as abas em que faz sentido.
- Empresa: lista com as empresas do cliente (vem do ERP). O fork esconde esse filtro para clientes
  cujo cadastro tem uma empresa só.

O script só muda perguntas e o painel no Metabase (pela API). Nenhum banco dos sistemas é alterado.
Rode primeiro sem --aplicar para ver o relatório.

Uso:
  export MB_URL=http://localhost:3002 MB_KEY=mb_...
  python3 bin/all-filtros-abas.py [--painel 20]
  python3 bin/all-filtros-abas.py --aplicar
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

PERIODOS = [["7d", "Últimos 7 dias"], ["30d", "Últimos 30 dias"], ["90d", "Últimos 90 dias"],
            ["12m", "Últimos 12 meses"], ["mes", "Este mês"], ["mes_passado", "Mês passado"],
            ["ano", "Este ano"], ["tudo", "Todo o período"]]

# aba (regex no nome) → configuração
TABS = [
    {"match": r"atendiment", "key": "atendimentos", "periodo": "12m", "dispositivo": True, "empresa": True},
    {"match": r"manuten", "key": "manutencoes", "periodo": "12m", "dispositivo": True, "empresa": True},
    {"match": r"backup", "key": "backup", "periodo": "30d", "dispositivo": False, "empresa": False},
    {"match": r"auditoria", "key": "auditoria", "periodo": "7d", "dispositivo": False, "empresa": False},
    {"match": r"navega", "key": "navegacao", "periodo": "7d", "dispositivo": True, "empresa": False},
    {"match": r"esta[cç]", "key": "estacoes", "periodo": None, "dispositivo": True, "empresa": False},
]

# perguntas que não fazem sentido com período (mostram o "último" de cada coisa)
SEM_PERIODO = {"Último backup por job"}

P = "{{periodo}}"
FB_P = "CAST({{periodo}} AS VARCHAR(20))"


def fb_inicio(default):
    return ("CASE " + FB_P + " WHEN '7d' THEN DATEADD(-7 DAY TO CURRENT_DATE)"
            " WHEN '30d' THEN DATEADD(-30 DAY TO CURRENT_DATE)"
            " WHEN '90d' THEN DATEADD(-90 DAY TO CURRENT_DATE)"
            " WHEN '12m' THEN DATEADD(-12 MONTH TO CURRENT_DATE)"
            " WHEN 'mes' THEN DATEADD(1 - EXTRACT(DAY FROM CURRENT_DATE) DAY TO CURRENT_DATE)"
            " WHEN 'mes_passado' THEN DATEADD(-1 MONTH TO DATEADD(1 - EXTRACT(DAY FROM CURRENT_DATE) DAY TO CURRENT_DATE))"
            " WHEN 'ano' THEN DATEADD(-EXTRACT(YEARDAY FROM CURRENT_DATE) DAY TO CURRENT_DATE)"
            " WHEN 'tudo' THEN DATE '1900-01-01'"
            " ELSE DATEADD(-12 MONTH TO CURRENT_DATE) END")


FB_FIM = ("CASE " + FB_P + " WHEN 'mes_passado' THEN DATEADD(1 - EXTRACT(DAY FROM CURRENT_DATE) DAY TO CURRENT_DATE)"
          " ELSE DATEADD(1 DAY TO CURRENT_DATE) END")


def pg_inicio(now="now()"):
    return ("CASE " + P + f" WHEN '7d' THEN {now} - interval '7 days'"
            f" WHEN '30d' THEN {now} - interval '30 days'"
            f" WHEN '90d' THEN {now} - interval '90 days'"
            f" WHEN '12m' THEN {now} - interval '12 months'"
            f" WHEN 'mes' THEN date_trunc('month', {now})"
            f" WHEN 'mes_passado' THEN date_trunc('month', {now}) - interval '1 month'"
            f" WHEN 'ano' THEN date_trunc('year', {now})"
            " WHEN 'tudo' THEN timestamp '1900-01-01'"
            f" ELSE {now} - interval '7 days' END")


def pg_fim(now="now()"):
    return ("CASE " + P + f" WHEN 'mes_passado' THEN date_trunc('month', {now}) ELSE {now} + interval '1 day' END")


EMPRESA_NOME = "COALESCE(NULLIF(TRIM(CE9.FANTASIA_CLI), ''), TRIM(CE9.NOME_CLI))"
EMPRESA_IN = "(SELECT CE9.CODCLI FROM CADCLI CE9 WHERE " + EMPRESA_NOME + " = {{empresa}})"

ATD_DISP = ("[[AND A.SERVICE_TAG_ATD IN (SELECT SD9.SERVICE_TAG_ASTAG FROM SERVICE_TAG SD9 "
            "WHERE SD9.DESCRICAO_ASTAG CONTAINING {{dispositivo}})]]")
ATD_EMP = ("[[AND COALESCE((SELECT FIRST 1 SE9.CLIENTE_ASTAG FROM SERVICE_TAG SE9 WHERE SE9.SERVICE_TAG_ASTAG = A.SERVICE_TAG_ATD), "
           "A.CLIENTE_ATD) IN " + EMPRESA_IN + "]]")
OS_DISP = ("[[AND EXISTS (SELECT 1 FROM CADCLI_OS_EQUIPAM ED9 JOIN SERVICE_TAG SD9 ON SD9.SERVICE_TAG_ASTAG = ED9.SERVICE_TAG_COEQ "
           "WHERE ED9.OS_COEQ = O.CODIGO_CLIOS AND ED9.EMPRESA_COEQ = O.EMPRESA_CLIOS AND SD9.DESCRICAO_ASTAG CONTAINING {{dispositivo}})]]")
OS_EMP = ("[[AND COALESCE((SELECT FIRST 1 SE9.CLIENTE_ASTAG FROM CADCLI_OS_EQUIPAM EE9 JOIN SERVICE_TAG SE9 "
          "ON SE9.SERVICE_TAG_ASTAG = EE9.SERVICE_TAG_COEQ WHERE EE9.OS_COEQ = O.CODIGO_CLIOS AND EE9.EMPRESA_COEQ = O.EMPRESA_CLIOS), "
          "O.CLIENTE_CLIOS) IN " + EMPRESA_IN + "]]")

NAV_NOW = "(now() AT TIME ZONE 'America/Sao_Paulo')"

EMPRESAS_SQL = """SELECT CAST(COALESCE(NULLIF(TRIM(C.FANTASIA_CLI), ''), TRIM(C.NOME_CLI)) AS VARCHAR(60) CHARACTER SET WIN1252) AS "Empresa"
FROM CADCLI C
WHERE C.CODCLI IN (__ALL_ERP__)
ORDER BY 1
/* {{all_cliente}} */"""


def rewrite(sql, tab):
    """Devolve (sql_novo, [tags usadas], [avisos])."""
    used, warns = [], []
    out = sql
    periodo = tab["periodo"]

    # --- ERP (Firebird): atendimentos e OS ---
    def erp(m):
        col = m.group(1)
        alias = col.split(".")[0]
        extra = ""
        if tab["dispositivo"]:
            extra += " " + (ATD_DISP if alias == "A" else OS_DISP)
        if tab["empresa"]:
            extra += " " + (ATD_EMP if alias == "A" else OS_EMP)
        return f"{col} >= {fb_inicio(periodo)} AND {col} < {FB_FIM}{extra}"

    out, n = re.subn(r"\b([AO]\.(?:DATAINICIO_ATD|DATA_CLIOS))\s*>=\s*DATEADD\(-12 MONTH TO CURRENT_DATE\)", erp, out)
    if n == 0 and "CADCLI_OS O" in out and "O.SITUACAO_CLIOS <> 0" in out and periodo:
        # OS sem janela de tempo (ex.: custo por dispositivo): acrescenta o período
        extra = f" AND O.DATA_CLIOS >= {fb_inicio(periodo)} AND O.DATA_CLIOS < {FB_FIM}"
        if tab["dispositivo"]:
            extra += " " + OS_DISP
        if tab["empresa"]:
            extra += " " + OS_EMP
        out, n = re.subn(r"(O\.SITUACAO_CLIOS <> 0)", lambda m: m.group(1) + extra, out, count=1)

    # --- Bacula / Wazuh (Postgres) ---
    if periodo:
        out, n2 = re.subn(r"((?:\w+\.)?(?:starttime|data_hora))\s*>=\s*now\(\)\s*-\s*interval\s*'\d+ (?:days|hours)'",
                          lambda m: f"{m.group(1)} >= {pg_inicio()} AND {m.group(1)} < {pg_fim()}", out)
        n += n2

    # --- Navegação (demo): 90 dias de dados + período + estação ---
    if "WHERE a.data_hora <= now() AT TIME ZONE 'America/Sao_Paulo'" in out:
        out = out.replace("% 7) * interval '1 day')", "% 90) * interval '1 day')")
        out = out.replace("generate_series(1, 2000 + abs(hashtext((SELECT cli FROM p))) % 1500)",
                          "generate_series(1, (2000 + abs(hashtext((SELECT cli FROM p))) % 1500) * 13)")
        cond = f"a.data_hora >= {pg_inicio(NAV_NOW)} AND a.data_hora < {pg_fim(NAV_NOW)}"
        disp = " [[AND u.estacao ILIKE '%' || {{dispositivo}} || '%']]" if tab["dispositivo"] else ""
        out = out.replace("WHERE a.data_hora <= now() AT TIME ZONE 'America/Sao_Paulo'",
                          f"WHERE a.data_hora <= {NAV_NOW} AND {cond}{disp}")
        n += 1

    # --- Estações (Tactical): só dispositivo ---
    if tab["key"] == "estacoes" and "c.name = '__ALL_TACTICAL__'" in out:
        out = out.replace("c.name = '__ALL_TACTICAL__'",
                          "c.name = '__ALL_TACTICAL__' [[AND a.hostname ILIKE '%' || {{dispositivo}} || '%']]", 1)

    for t in ("periodo", "dispositivo", "empresa"):
        if "{{" + t + "}}" in out:
            used.append(t)
    if periodo and "periodo" not in used:
        warns.append("sem filtro de período (não achei a coluna de data)")
    return out, used, warns


def tag_def(name, default=None):
    labels = {"periodo": "Período", "dispositivo": "Dispositivo", "empresa": "Empresa"}
    t = {"id": f"all-{name}", "name": name, "display-name": labels[name], "type": "text"}
    if default:
        t["default"] = default
    return t


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


def card_parts(card):
    dq = card["dataset_query"]
    if "native" in dq:
        return dq["native"]["query"], dict(dq["native"].get("template-tags") or {})
    st = dq["stages"][0]
    tl = st.get("template-tags") or []
    return st["native"], ({t["name"]: t for t in tl} if isinstance(tl, list) else dict(tl))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--painel", type=int, default=20)
    args = ap.parse_args()
    api = Api(os.environ.get("MB_URL", ""), os.environ.get("MB_KEY", ""))
    if not api.url or not api.key:
        sys.exit("Defina MB_URL e MB_KEY.")

    dash = api.call("GET", f"/api/dashboard/{args.painel}")
    params = dash.get("parameters") or []
    by_slug = {p["slug"]: p for p in params}
    cliente = by_slug.get("cliente")
    if not cliente:
        sys.exit("Painel sem o filtro 'cliente'.")
    erp_db = coll = None

    plan = []  # (dashcard, tab_cfg, card, new_sql, tags, used)
    tabs = {t["id"]: t["name"] for t in dash.get("tabs") or []}
    for dc in dash["dashcards"]:
        card = dc.get("card") or {}
        if not card.get("id"):
            continue
        tab_name = tabs.get(dc.get("dashboard_tab_id"), "")
        cfg = next((t for t in TABS if re.search(t["match"], tab_name, re.I)), None)
        if not cfg:
            continue
        sql, tags = card_parts(card)
        if "__ALL_ERP__" in sql and erp_db is None:
            erp_db, coll = card["database_id"], card["collection_id"]
        if "{{periodo}}" in sql or "{{dispositivo}}" in sql:
            print(f"  = {tab_name} | {card['name']}: já tem filtros, mantido")
            plan.append((dc, cfg, card, None, tags, [t for t in ("periodo", "dispositivo", "empresa") if "{{" + t + "}}" in sql]))
            continue
        cfg2 = dict(cfg)
        if card["name"] in SEM_PERIODO:
            cfg2["periodo"] = None
        new_sql, used, warns = rewrite(sql, cfg2)
        print(f"  - {tab_name} | {card['name']}: {', '.join(used) or 'nenhum filtro'}"
              + (f"  ATENÇÃO: {'; '.join(warns)}" if warns else ""))
        plan.append((dc, cfg2, card, new_sql, tags, used))

    if not args.aplicar:
        print("\nNada foi alterado. Rode com --aplicar.")
        return

    # filtros do painel
    def ensure_param(slug, name, extra):
        if slug in by_slug:
            return by_slug[slug]
        p = {"id": f"all_{slug}", "name": name, "slug": slug, "sectionId": "string", "type": "string/="}
        p.update(extra)
        params.append(p)
        by_slug[slug] = p
        return p

    empresas_card = None
    if any(c["empresa"] for (_, c, _, _, _, used) in plan if "empresa" in used):
        empresas_card = api.call("POST", "/api/card", {
            "name": "Empresas do cliente", "display": "table", "collection_id": coll,
            "description": "Lista do filtro Empresa (empresas do cliente no ERP).",
            "visualization_settings": {},
            "dataset_query": {"database": erp_db, "type": "native", "native": {
                "query": EMPRESAS_SQL,
                "template-tags": {"all_cliente": {"id": "all-cliente-emp", "name": "all_cliente",
                                                  "display-name": "Cliente", "type": "text",
                                                  "default": (cliente.get("default") or [None])[0]}}}},
        })
        print(f"  + pergunta {empresas_card['id']}: Empresas do cliente (lista do filtro Empresa)")

    for (dc, cfg, card, new_sql, tags, used) in plan:
        if cfg["periodo"] and "periodo" in used:
            ensure_param(f"periodo_{cfg['key']}", "Período", {
                "default": [cfg["periodo"]], "values_query_type": "list",
                "values_source_type": "static-list", "values_source_config": {"values": PERIODOS},
                "required": True})
        if "dispositivo" in used:
            ensure_param("dispositivo", "Dispositivo", {"values_query_type": "none"})
        if "empresa" in used and empresas_card:
            ensure_param("empresa", "Empresa", {
                "values_query_type": "list", "values_source_type": "card",
                "values_source_config": {"card_id": empresas_card["id"],
                                         "value_field": ["field", "Empresa", {"base-type": "type/Text"}]}})

    for (dc, cfg, card, new_sql, tags, used) in plan:
        if new_sql is not None:
            for t in used:
                tags[t] = tag_def(t, cfg["periodo"] if t == "periodo" else None)
            card_params = [{"id": tg["id"], "type": "category", "name": tg.get("display-name", n), "slug": n,
                            "target": ["variable", ["template-tag", n]],
                            **({"default": tg["default"]} if tg.get("default") else {})}
                           for n, tg in tags.items()]
            new_name = re.sub(r"\s*\((7|30) dias\)$|\s*\(12 meses\)$", "", card["name"])
            api.call("PUT", f"/api/card/{card['id']}", {
                "name": new_name,
                "dataset_query": {"database": card["database_id"], "type": "native",
                                  "native": {"query": new_sql, "template-tags": tags}},
                "parameters": card_params})
        maps = [m for m in (dc.get("parameter_mappings") or [])
                if m["parameter_id"] not in {by_slug.get(s, {}).get("id") for s in
                                             (f"periodo_{cfg['key']}", "dispositivo", "empresa")}]
        for t in used:
            slug = f"periodo_{cfg['key']}" if t == "periodo" else t
            if slug in by_slug:
                maps.append({"parameter_id": by_slug[slug]["id"], "card_id": card["id"],
                             "target": ["variable", ["template-tag", t]]})
        dc["parameter_mappings"] = maps

    keep = [{k: dc.get(k) for k in ("id", "card_id", "dashboard_tab_id", "row", "col", "size_x", "size_y",
                                    "parameter_mappings", "visualization_settings", "series")}
            for dc in dash["dashcards"]]
    api.call("PUT", f"/api/dashboard/{args.painel}", {
        "parameters": params,
        "tabs": [{"id": t["id"], "name": t["name"]} for t in dash.get("tabs") or []],
        "dashcards": keep,
    })
    print("Filtros aplicados:", ", ".join(p["slug"] for p in params))


if __name__ == "__main__":
    main()
