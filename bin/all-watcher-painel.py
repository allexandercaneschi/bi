#!/usr/bin/env python3
"""
ALL Tecnologias - aba "Monitoramento de atividade" (ALL Watcher) no painel modelo do ALL B.I.

Cria as perguntas (SQL sobre as views do schema `bi` do banco do ALL Watcher, com o marcador __ALL_WATCHER__),
a aba "Monitoramento de atividade" no painel modelo e o filtro "Colaborador". Os filtros "Cliente", "Data inicial"
e "Data final" do painel modelo sao reaproveitados. Sem data escolhida: ultimos 7 dias.

Linguagem pensada para quem nao e de TI: "tempo trabalhando", "programas produtivos", "fora do trabalho".
Tipos: Produtivo / Neutro / Fora do trabalho (classificacao por programa e por site: tabelas categorias_app
e categorias_site do ALL Watcher). "Parado" (sem teclado/mouse) nao conta como tempo trabalhando.

Uso:
  export MB_URL=http://localhost:3002 MB_KEY=mb_...
  python3 all-watcher-painel.py                       # mostra o plano
  python3 all-watcher-painel.py --aplicar [--banco "ALL Watcher"] [--painel 20]
  python3 all-watcher-painel.py --aplicar --grupo-demo   # cria o grupo "Empresa Exemplo (demo)" com o codigo demo-exemplo

Rodar de novo recria a aba (as perguntas antigas da aba sao arquivadas).
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

TAB_NAME = "Monitoramento de atividade"
CLIENT_TAG = "all_cliente"
GREEN, GRAY, ORANGE, YELLOW = "#1baf7a", "#a3a29a", "#eb6834", "#eda100"

TIPO = ("CASE n.categoria WHEN 'produtivo' THEN 'Produtivo' WHEN 'neutro' THEN 'Neutro' "
        "WHEN 'improdutivo' THEN 'Fora do trabalho' ELSE 'Parado' END")
HM = "(({m}) / 60)::int || 'h ' || lpad((({m}) % 60)::int::text, 2, '0') || 'min'"

# Janela de datas e filtro de colaborador comuns a todas as perguntas da atividade
BASE = """WITH n AS (
  SELECT a.*
  FROM bi.atividade a
  WHERE a.cliente = '__ALL_WATCHER__'
    AND a.dia >= COALESCE(NULL[[, {{data_inicial}}::date]], (now() AT TIME ZONE 'America/Sao_Paulo')::date - 6)
    AND a.dia <= COALESCE(NULL[[, {{data_final}}::date]], (now() AT TIME ZONE 'America/Sao_Paulo')::date)
    [[AND a.colaborador = {{colaborador}}]]
)
"""

CARDS = [
    {"name": "Colaboradores monitorados", "display": "scalar", "size": (6, 3), "use": "n",
     "sql": 'SELECT count(DISTINCT n.colaborador) AS "Colaboradores" FROM n', "viz": {}},
    {"name": "Tempo trabalhando por dia", "display": "scalar", "size": (6, 3), "use": "n",
     "description": "Média por colaborador nos dias em que usou o computador. Não conta o tempo parado.",
     "sql": ("SELECT " + HM.format(m="COALESCE(sum(n.seg_ativo) / NULLIF(count(DISTINCT (n.colaborador, n.dia)), 0) / 60, 0)")
             + ' AS "Por colaborador, por dia" FROM n'), "viz": {}},
    {"name": "Tempo em programas produtivos", "display": "scalar", "size": (6, 3), "use": "n",
     "description": "Parte do tempo trabalhando que foi em programas e sites do trabalho (ERP, Office, e-mail...).",
     "sql": ("SELECT COALESCE(round(100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'produtivo') "
             "/ NULLIF(sum(n.seg_ativo), 0)), 0)::int || '%' AS \"Produtivo\" FROM n"), "viz": {}},
    {"name": "Tempo fora do trabalho", "display": "scalar", "size": (6, 3), "use": "n",
     "description": "Parte do tempo trabalhando que foi em redes sociais, vídeos, jogos e similares.",
     "sql": ("SELECT COALESCE(round(100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'improdutivo') "
             "/ NULLIF(sum(n.seg_ativo), 0)), 0)::int || '%' AS \"Fora do trabalho\" FROM n"), "viz": {}},

    {"name": "Como o tempo foi usado", "display": "pie", "size": (8, 7), "use": "n",
     "description": "Divisão do tempo trabalhando entre programas produtivos, neutros e fora do trabalho.",
     "sql": ("SELECT " + TIPO + ' AS "Tipo", round(sum(n.seg_ativo) / 3600.0, 1) AS "Horas" '
             "FROM n WHERE n.categoria <> 'parado' GROUP BY 1 ORDER BY 2 DESC"),
     "viz": {"pie.dimension": "Tipo", "pie.metric": "Horas", "pie.show_legend": True,
             "pie.percent_visibility": "inside",
             "pie.colors": {"Produtivo": GREEN, "Neutro": GRAY, "Fora do trabalho": ORANGE}}},
    {"name": "Dia a dia", "display": "bar", "size": (16, 7), "use": "n",
     "description": "Horas trabalhadas em cada dia, separadas por tipo de uso.",
     "sql": ("SELECT n.dia AS \"Dia\", " + TIPO + ' AS "Tipo", round(sum(n.seg_ativo) / 3600.0, 1) AS "Horas" '
             "FROM n WHERE n.categoria <> 'parado' GROUP BY 1, 2 ORDER BY 1"),
     "viz": {"graph.dimensions": ["Dia", "Tipo"], "graph.metrics": ["Horas"], "stackable.stack_type": "stacked",
             "graph.x_axis.title_text": "", "graph.y_axis.title_text": "Horas",
             "series_settings": {"Produtivo": {"color": GREEN}, "Neutro": {"color": GRAY},
                                 "Fora do trabalho": {"color": ORANGE}}}},

    {"name": "Colaboradores", "display": "table", "size": (24, 7), "use": "n", "click_colaborador": True,
     "description": "Clique no nome para ver só aquele colaborador na página inteira.",
     "sql": ('SELECT n.colaborador AS "Colaborador", count(DISTINCT n.dia) AS "Dias de uso", '
             + HM.format(m="sum(n.seg_ativo) / NULLIF(count(DISTINCT n.dia), 0) / 60") + ' AS "Tempo por dia", '
             "COALESCE(round(100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'produtivo') "
             "/ NULLIF(sum(n.seg_ativo), 0)), 0)::int AS \"Produtivo (%)\", "
             "COALESCE(round(100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'improdutivo') "
             "/ NULLIF(sum(n.seg_ativo), 0)), 0)::int AS \"Fora do trabalho (%)\", "
             "max(n.fim) AS \"Último uso\" FROM n GROUP BY 1 ORDER BY 5 DESC, 1"),
     "viz": {"table.column_formatting": [
         {"columns": ["Fora do trabalho (%)"], "type": "single", "operator": ">=", "value": 25,
          "color": ORANGE, "highlight_row": False},
         {"columns": ["Fora do trabalho (%)"], "type": "single", "operator": "<", "value": 25,
          "color": GREEN, "highlight_row": False},
         {"columns": ["Produtivo (%)"], "type": "single", "operator": ">=", "value": 60,
          "color": GREEN, "highlight_row": False},
         {"columns": ["Produtivo (%)"], "type": "single", "operator": "<", "value": 40,
          "color": YELLOW, "highlight_row": False}]}},

    {"name": "Uso ao longo do dia", "display": "bar", "size": (12, 7), "use": "n",
     "description": "Em quais horas do dia o computador é mais usado (soma do período).",
     "sql": ("SELECT lpad(n.hora::text, 2, '0') || 'h' AS \"Hora\", " + TIPO + ' AS "Tipo", '
             'round(sum(n.seg_ativo) / 3600.0, 1) AS "Horas" '
             "FROM n WHERE n.categoria <> 'parado' GROUP BY n.hora, 2 ORDER BY n.hora"),
     "viz": {"graph.dimensions": ["Hora", "Tipo"], "graph.metrics": ["Horas"], "stackable.stack_type": "stacked",
             "graph.y_axis.title_text": "Horas",
             "series_settings": {"Produtivo": {"color": GREEN}, "Neutro": {"color": GRAY},
                                 "Fora do trabalho": {"color": ORANGE}}}},
    {"name": "Computadores agora", "display": "table", "size": (12, 7), "use": "d",
     "description": "Quem está usando o computador neste momento. Atualiza sozinho.",
     "sql": ('SELECT d.colaborador AS "Colaborador", d.dispositivo AS "Computador", d.situacao AS "Situação", '
             'd.ultimo_contato AS "Último contato" FROM bi.dispositivos d '
             "WHERE d.cliente = '__ALL_WATCHER__' AND d.ativo "
             "ORDER BY CASE d.situacao WHEN 'Em uso' THEN 0 WHEN 'Sem contato hoje' THEN 1 ELSE 2 END, 1"),
     "viz": {"table.column_formatting": [
         {"columns": ["Situação"], "type": "single", "operator": "=", "value": "Em uso", "color": GREEN, "highlight_row": False},
         {"columns": ["Situação"], "type": "single", "operator": "=", "value": "Sem contato hoje", "color": YELLOW, "highlight_row": False},
         {"columns": ["Situação"], "type": "single", "operator": "contains", "value": "mais de 1 dia", "color": ORANGE, "highlight_row": False}]}},

    {"name": "Onde o tempo foi gasto", "display": "table", "size": (14, 8), "use": "n",
     "description": "Programas e sites mais usados, com o tipo de cada um. Para mudar o tipo, fale com a ALL.",
     "sql": ('SELECT n.programa AS "Programa ou site", ' + TIPO + ' AS "Tipo", '
             + HM.format(m="sum(n.seg_ativo) / 60") + ' AS "Tempo", round(sum(n.seg_ativo) / 3600.0, 1) AS "Horas" '
             "FROM n WHERE n.categoria <> 'parado' GROUP BY 1, 2 ORDER BY 4 DESC LIMIT 15"),
     "viz": {"table.column_formatting": [
         {"columns": ["Tipo"], "type": "single", "operator": "=", "value": "Produtivo", "color": GREEN, "highlight_row": False},
         {"columns": ["Tipo"], "type": "single", "operator": "=", "value": "Neutro", "color": GRAY, "highlight_row": False},
         {"columns": ["Tipo"], "type": "single", "operator": "=", "value": "Fora do trabalho", "color": ORANGE, "highlight_row": False}]}},
    {"name": "Pontos de atenção", "display": "table", "size": (10, 8), "use": "nd",
     "description": "Só aparece o que foge do normal.",
     "sql": ("""SELECT msg AS "O que chamou a atenção" FROM (
  SELECT 1 AS o, format('%s passou %s%% do tempo em programas e sites fora do trabalho (média da equipe: %s%%).',
                        t.colaborador, t.pct, t.media) AS msg
  FROM (SELECT x.colaborador, x.pct, round(avg(x.pct) OVER ())::int AS media
        FROM (SELECT n.colaborador,
                     round(100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'improdutivo') / NULLIF(sum(n.seg_ativo), 0))::int AS pct
              FROM n GROUP BY 1) x WHERE x.pct IS NOT NULL) t
  WHERE t.pct >= 25
  UNION ALL
  SELECT 2, format('%s (%s) está sem enviar dados há mais de 1 dia. Pode estar desligado ou sem internet.', d.dispositivo, d.colaborador)
  FROM bi.dispositivos d
  WHERE d.cliente = '__ALL_WATCHER__' AND d.ativo AND d.situacao = 'Sem contato ha mais de 1 dia'
  UNION ALL
  SELECT 3, 'Nada fora do normal neste período.'
  WHERE NOT EXISTS (SELECT 1 FROM n GROUP BY n.colaborador HAVING
          100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'improdutivo') / NULLIF(sum(n.seg_ativo), 0) >= 25)
    AND NOT EXISTS (SELECT 1 FROM bi.dispositivos d WHERE d.cliente = '__ALL_WATCHER__' AND d.ativo
                    AND d.situacao = 'Sem contato ha mais de 1 dia')
) z ORDER BY o, msg"""), "viz": {}},

    {"name": "Telas capturadas", "display": "table", "size": (24, 8), "use": "p",
     "description": "Imagens da tela do colaborador, uma a cada alguns minutos. Clique em \"Abrir tela\" para ampliar.",
     "sql": ('SELECT p.capturado_em AS "Quando", p.colaborador AS "Colaborador", p.dispositivo AS "Computador", '
             'p.programa AS "Programa ou site", p.url AS "Tela" FROM bi.prints p '
             "WHERE p.cliente = '__ALL_WATCHER__' "
             "AND p.dia >= COALESCE(NULL[[, {{data_inicial}}::date]], (now() AT TIME ZONE 'America/Sao_Paulo')::date - 6) "
             "AND p.dia <= COALESCE(NULL[[, {{data_final}}::date]], (now() AT TIME ZONE 'America/Sao_Paulo')::date) "
             "[[AND p.colaborador = {{colaborador}}]] ORDER BY p.capturado_em DESC LIMIT 24"),
     "viz": {"column_settings": {'["name","Tela"]': {"view_as": "link", "link_text": "Abrir tela", "link_url": "{{Tela}}"}}}},
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
            sys.exit(f"Erro {e.code} em {method} {path}: {e.read().decode(errors='replace')[:600]}")


def full_sql(c):
    base = BASE if "n" in c["use"] else ""
    return base + c["sql"] + "\n/* {{" + CLIENT_TAG + "}} */"


def tags_for(sql):
    tags = {}
    for name in sorted(set(re.findall(r"\{\{\s*(\w+)\s*\}\}", sql))):
        tags[name] = {"id": f"all-w-{name}", "name": name, "type": "text",
                      "display-name": {"all_cliente": "Cliente", "data_inicial": "Data inicial",
                                       "data_final": "Data final", "colaborador": "Colaborador"}.get(name, name)}
    return tags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--painel", type=int, default=20)
    ap.add_argument("--banco", default="ALL Watcher")
    ap.add_argument("--grupo-demo", action="store_true")
    args = ap.parse_args()
    api = Api(os.environ.get("MB_URL", ""), os.environ.get("MB_KEY", ""))
    if not api.url or not api.key:
        sys.exit("Defina MB_URL e MB_KEY.")

    dbs = api.call("GET", "/api/database")
    dbs = dbs["data"] if isinstance(dbs, dict) else dbs
    db = next((d for d in dbs if d["name"].strip().lower() == args.banco.strip().lower()), None)
    if not db:
        sys.exit(f"Banco '{args.banco}' nao encontrado no Metabase. Cadastre em Admin > Bancos de dados.")

    dash = api.call("GET", f"/api/dashboard/{args.painel}")
    param = {p["slug"]: p for p in dash.get("parameters") or []}
    for need in ("cliente", "data_inicial", "data_final"):
        if need not in param:
            sys.exit(f"O painel nao tem o filtro '{need}'.")
    coll = next((dc["card"].get("collection_id") for dc in dash["dashcards"] if dc.get("card")), None)
    print(f"Painel: {dash['name']} - banco {db['name']} ({db['id']}) - pasta {coll}")
    for c in CARDS:
        print(f"  - {c['name']} ({c['display']})")
    if not args.aplicar:
        print("\nNada foi criado. Rode com --aplicar.")
        return

    # filtro Colaborador (lista alimentada por uma pergunta)
    lista_sql = ("SELECT DISTINCT a.colaborador AS \"Colaborador\" FROM bi.atividade a "
                 "WHERE a.cliente = '__ALL_WATCHER__' ORDER BY 1\n/* {{all_cliente}} */")
    for item in api.call("GET", f"/api/collection/{coll}/items?models=card")["data"]:
        if item["name"].startswith("Lista · Colaborador (watcher)"):
            api.call("PUT", f"/api/card/{item['id']}", {"archived": True})
    lista = api.call("POST", "/api/card", {
        "name": "Lista · Colaborador (watcher)", "display": "table", "collection_id": coll,
        "description": "Fonte do filtro Colaborador.", "visualization_settings": {},
        "dataset_query": {"database": db["id"], "type": "native",
                          "native": {"query": lista_sql, "template-tags": tags_for(lista_sql)}}})
    cliente = param["cliente"]
    colab = {"id": "all_colaborador", "name": "Colaborador", "slug": "colaborador", "type": "string/=",
             "sectionId": "string", "values_query_type": "list", "filteringParameters": [cliente["id"]],
             "values_source_type": "card",
             "values_source_config": {"card_id": lista["id"],
                                      "value_field": ["field", "Colaborador", {"base-type": "type/Text"}]}}
    params = [p for p in dash["parameters"] if p["slug"] != "colaborador"] + [colab]

    # aba (recria)
    tabs = [{"id": t["id"], "name": t["name"]} for t in dash["tabs"]]
    old = next((t for t in dash["tabs"] if re.search(r"monitora", t["name"], re.I)), None)
    keep = [dc for dc in dash["dashcards"] if not old or dc.get("dashboard_tab_id") != old["id"]]
    for dc in dash["dashcards"]:
        if old and dc.get("dashboard_tab_id") == old["id"] and dc.get("card_id"):
            api.call("PUT", f"/api/card/{dc['card_id']}", {"archived": True})
    tab_id = old["id"] if old else -1
    if not old:
        tabs.append({"id": tab_id, "name": TAB_NAME})

    new, col, row, line_h = [], 0, 3, 0
    new.append({
        "id": -1, "card_id": None, "dashboard_tab_id": tab_id, "row": 0, "col": 0, "size_x": 24, "size_y": 3,
        "parameter_mappings": [], "series": [],
        "visualization_settings": {
            "virtual_card": {"name": None, "display": "text", "visualization_settings": {},
                             "dataset_query": {}, "archived": False},
            "text": ("**Como ler esta página.** Os números mostram como o tempo de trabalho foi usado no computador. "
                     "**Produtivo** são os programas e sites do trabalho, **Neutro** são os de uso geral (navegador, "
                     "mensagens) e **Fora do trabalho** são redes sociais, vídeos e jogos. O tempo em que o computador "
                     "ficou parado não conta. Sem escolher datas, a página mostra os últimos 7 dias.")}})
    for i, c in enumerate(CARDS):
        w, h = c["size"]
        if col + w > 24:
            row, col, line_h = row + line_h, 0, 0
        sql = full_sql(c)
        viz = json.loads(json.dumps(c["viz"]))
        created = api.call("POST", "/api/card", {
            "name": c["name"], "display": c["display"], "collection_id": coll,
            "description": c.get("description"), "visualization_settings": viz,
            "dataset_query": {"database": db["id"], "type": "native",
                              "native": {"query": sql, "template-tags": tags_for(sql)}}})
        used = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", sql))
        maps = [{"parameter_id": cliente["id"], "card_id": created["id"],
                 "target": ["variable", ["template-tag", CLIENT_TAG]]}]
        for slug in ("data_inicial", "data_final", "colaborador"):
            if slug in used:
                pid = colab["id"] if slug == "colaborador" else param[slug]["id"]
                maps.append({"parameter_id": pid, "card_id": created["id"],
                             "target": ["variable", ["template-tag", slug]]})
        dviz = {}
        if c.get("click_colaborador"):
            dviz["column_settings"] = {'["name","Colaborador"]': {"click_behavior": {
                "type": "crossfilter", "parameterMapping": {colab["id"]: {
                    "id": colab["id"], "source": {"type": "column", "id": "Colaborador", "name": "Colaborador"},
                    "target": {"type": "parameter", "id": colab["id"]}}}}}}
        new.append({"id": -(i + 2), "card_id": created["id"], "dashboard_tab_id": tab_id,
                    "row": row, "col": col, "size_x": w, "size_y": h,
                    "visualization_settings": dviz, "series": [], "parameter_mappings": maps})
        print(f"  + pergunta {created['id']}: {c['name']}")
        col += w
        line_h = max(line_h, h)

    keep_cards = [{k: dc.get(k) for k in ("id", "card_id", "dashboard_tab_id", "row", "col", "size_x", "size_y",
                                          "parameter_mappings", "visualization_settings", "series")} for dc in keep]
    api.call("PUT", f"/api/dashboard/{args.painel}", {"parameters": params, "tabs": tabs, "dashcards": keep_cards + new})
    print(f"Aba '{TAB_NAME}' criada com {len(CARDS)} perguntas.")

    if args.grupo_demo:
        groups = api.call("GET", "/api/permissions/group")
        nome = "Empresa Exemplo (demo)"
        g = next((x for x in groups if x["name"] == nome), None) or api.call("POST", "/api/permissions/group", {"name": nome})
        ids = api.call("GET", "/api/setting/all-client-group-ids") or []
        if g["id"] not in ids:
            api.call("PUT", "/api/setting/all-client-group-ids", {"value": ids + [g["id"]]})
        config = api.call("GET", "/api/setting/all-client-group-config") or {}
        cfg = config.get(str(g["id"])) or {"codes": {}, "services": {}}
        cfg.setdefault("codes", {})["watcher"] = "demo-exemplo"
        cfg.setdefault("services", {})["monitoramento"] = True
        config[str(g["id"])] = cfg
        api.call("PUT", "/api/setting/all-client-group-config", {"value": config})
        print(f"Grupo '{nome}' (id {g['id']}): codigo watcher = demo-exemplo, servico monitoramento ligado.")


if __name__ == "__main__":
    main()
