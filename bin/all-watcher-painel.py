#!/usr/bin/env python3
"""
ALL Tecnologias - "Monitoramento de atividade" (ALL Watcher) no painel modelo do ALL B.I.

Cria as perguntas (SQL sobre as views do schema `bi` do banco do ALL Watcher, com o marcador __ALL_WATCHER__),
tres sub-abas no painel modelo ("Monitoramento de atividade › Visão geral", "› Dia do colaborador" e
"› Mapa da semana"; o fork mostra o " › " como aba dentro de aba) e os filtros "Colaborador" e "Período"
(o mesmo filtro de datas do Metabase usado em "Atendimentos e Contratos"; padrao: Hoje; no mapa da semana:
ultimos 7 dias). O filtro "Cliente" do painel modelo e reaproveitado.

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
SEP = " › "
CLIENT_TAG = "all_cliente"
GREEN, GRAY, ORANGE, YELLOW = "#1baf7a", "#a3a29a", "#eb6834", "#eda100"

TIPO = ("CASE n.categoria WHEN 'produtivo' THEN 'Produtivo' WHEN 'neutro' THEN 'Neutro' "
        "WHEN 'improdutivo' THEN 'Fora do trabalho' ELSE 'Parado' END")
HM = "(({m}) / 60)::int || 'h ' || lpad((({m}) % 60)::int::text, 2, '0') || 'min'"

# Periodo (filtro de campo do Metabase) e colaborador, comuns a todas as perguntas da atividade.
# O filtro de campo vira "bi"."atividade"."dia" ..., por isso a tabela nao pode ter apelido.
BASE = """WITH n AS (
  SELECT * FROM bi.atividade
  WHERE cliente = '__ALL_WATCHER__'
    AND {{periodo}}
    [[AND colaborador = {{colaborador}}]]
)
"""

PCT_PROD = ("COALESCE(round(100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'produtivo') "
            "/ NULLIF(sum(n.seg_ativo), 0)), 0)::int")
PCT_NEUTRO = ("COALESCE(round(100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'neutro') "
              "/ NULLIF(sum(n.seg_ativo), 0)), 0)::int")
PCT_FORA = ("COALESCE(round(100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'improdutivo') "
            "/ NULLIF(sum(n.seg_ativo), 0)), 0)::int")
ORDEM_TIPO = ("CASE n.categoria WHEN 'produtivo' THEN 1 WHEN 'neutro' THEN 2 WHEN 'improdutivo' THEN 3 ELSE 4 END")
DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

# Visualizacoes proprias do fork (ALL-FORK.md, "Visualizações próprias"): leem as colunas pelo nome.
CARDS = [
    {"name": "Colaboradores monitorados", "display": "custom:all-indicador", "size": (6, 3), "use": "n",
     "sql": ('SELECT count(DISTINCT n.colaborador) AS "Colaboradores", '
             "'usaram o computador no período' AS \"Detalhe\", 'azul' AS \"Cor\" FROM n"), "viz": {}},
    {"name": "Tempo trabalhando por dia", "display": "custom:all-indicador", "size": (6, 3), "use": "n",
     "description": "Média por colaborador nos dias em que usou o computador. Não conta o tempo parado.",
     "sql": ("SELECT " + HM.format(m="COALESCE(sum(n.seg_ativo) / NULLIF(count(DISTINCT (n.colaborador, n.dia)), 0) / 60, 0)")
             + ' AS "Por colaborador, por dia", '
             "'média por pessoa, por dia (sem o tempo parado)' AS \"Detalhe\", 'azul' AS \"Cor\" FROM n"), "viz": {}},
    {"name": "Tempo em programas produtivos", "display": "custom:all-indicador", "size": (6, 3), "use": "n",
     "description": "Parte do tempo trabalhando que foi em programas e sites do trabalho (ERP, Office, e-mail...).",
     "sql": ("SELECT " + PCT_PROD + " AS \"Produtivo\", '%' AS \"Sufixo\", "
             "'do tempo foi em programas do trabalho' AS \"Detalhe\", "
             "CASE WHEN " + PCT_PROD + " >= 60 THEN 'verde' WHEN " + PCT_PROD + " < 40 THEN 'amarelo' ELSE 'cinza' END "
             "AS \"Cor\" FROM n"), "viz": {}},
    {"name": "Tempo fora do trabalho", "display": "custom:all-indicador", "size": (6, 3), "use": "n",
     "description": "Parte do tempo trabalhando que foi em redes sociais, vídeos, jogos e similares.",
     "sql": ("SELECT " + PCT_FORA + " AS \"Fora do trabalho\", '%' AS \"Sufixo\", "
             "'em redes sociais, vídeos, jogos e similares' AS \"Detalhe\", "
             "CASE WHEN " + PCT_FORA + " >= 25 THEN 'laranja' ELSE 'verde' END AS \"Cor\" FROM n"), "viz": {}},

    {"name": "Como o tempo foi usado", "display": "custom:all-proporcao", "size": (24, 4), "use": "n",
     "description": "Divisão do tempo trabalhando entre programas produtivos, neutros e fora do trabalho.",
     "sql": ("SELECT " + TIPO + ' AS "Tipo", round(sum(n.seg_ativo) / 3600.0, 1) AS "Horas" '
             "FROM n WHERE n.categoria <> 'parado' GROUP BY 1, " + ORDEM_TIPO + " ORDER BY " + ORDEM_TIPO),
     "viz": {"all.unidade": "h"}},

    {"name": "Colaboradores", "display": "custom:all-pessoas", "size": (16, 9), "use": "n", "click_colaborador": True,
     "description": "Clique num cartão para ver só aquele colaborador na página inteira.",
     "sql": ('SELECT n.colaborador AS "Colaborador", '
             + HM.format(m="sum(n.seg_ativo) / NULLIF(count(DISTINCT n.dia), 0) / 60") + ' AS "Tempo por dia", '
             'count(DISTINCT n.dia) AS "Dias de uso", '
             + PCT_PROD + ' AS "Produtivo (%)", ' + PCT_NEUTRO + ' AS "Neutro (%)", ' + PCT_FORA + ' AS "Fora do trabalho (%)", '
             "max(n.fim) AS \"Último uso\" FROM n GROUP BY 1 ORDER BY 6 DESC, 1"),
     "viz": {}},
    {"name": "Pontos de atenção", "display": "custom:all-avisos", "size": (8, 9), "use": "nd",
     "description": "Só aparece o que foge do normal.",
     "sql": ("""SELECT msg AS "O que chamou a atenção", nivel AS "Nível" FROM (
  SELECT 1 AS o, 'atencao' AS nivel,
         format('%s passou %s%% do tempo em programas e sites fora do trabalho (média da equipe: %s%%).',
                t.colaborador, t.pct, t.media) AS msg
  FROM (SELECT x.colaborador, x.pct, round(avg(x.pct) OVER ())::int AS media
        FROM (SELECT n.colaborador,
                     round(100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'improdutivo') / NULLIF(sum(n.seg_ativo), 0))::int AS pct
              FROM n GROUP BY 1) x WHERE x.pct IS NOT NULL) t
  WHERE t.pct >= 25
  UNION ALL
  SELECT 0, 'alerta', format('%s (%s) está sem enviar dados há mais de 1 dia. Pode estar desligado ou sem internet.', d.dispositivo, d.colaborador)
  FROM bi.dispositivos d
  WHERE d.cliente = '__ALL_WATCHER__' AND d.ativo AND d.situacao = 'Sem contato ha mais de 1 dia'
  UNION ALL
  SELECT 3, 'ok', 'Nada fora do normal neste período.'
  WHERE NOT EXISTS (SELECT 1 FROM n GROUP BY n.colaborador HAVING
          100.0 * sum(n.seg_ativo) FILTER (WHERE n.categoria = 'improdutivo') / NULLIF(sum(n.seg_ativo), 0) >= 25)
    AND NOT EXISTS (SELECT 1 FROM bi.dispositivos d WHERE d.cliente = '__ALL_WATCHER__' AND d.ativo
                    AND d.situacao = 'Sem contato ha mais de 1 dia')
) z ORDER BY o, msg"""), "viz": {}},

    {"name": "Dia a dia", "display": "bar", "size": (24, 6), "use": "n",
     "description": "Horas trabalhadas em cada dia, separadas por tipo de uso.",
     "sql": ("SELECT n.dia AS \"Dia\", " + TIPO + ' AS "Tipo", round(sum(n.seg_ativo) / 3600.0, 1) AS "Horas" '
             "FROM n WHERE n.categoria <> 'parado' GROUP BY 1, 2 ORDER BY 1"),
     "viz": {"graph.dimensions": ["Dia", "Tipo"], "graph.metrics": ["Horas"], "stackable.stack_type": "stacked",
             "graph.x_axis.title_text": "", "graph.y_axis.title_text": "Horas",
             "series_settings": {"Produtivo": {"color": GREEN}, "Neutro": {"color": GRAY},
                                 "Fora do trabalho": {"color": ORANGE}}}},

    {"name": "Resumo do dia", "display": "custom:all-indicador", "size": (24, 3), "use": "n",
     "description": "Escolha um colaborador no filtro Colaborador (ou clique no cartão dele na aba Visão geral).",
     "sql": ("SELECT CASE WHEN count(DISTINCT n.colaborador) = 1 THEN max(n.colaborador) || ' usou o computador em ' "
             "|| count(DISTINCT n.dia) || CASE WHEN count(DISTINCT n.dia) = 1 THEN ' dia' ELSE ' dias' END || ': ' || ("
             + HM.format(m="COALESCE(sum(n.seg_ativo) / 60, 0)") + ") || ' trabalhando, ' || " + PCT_PROD +
             " || '% em programas produtivos.' "
             "WHEN count(DISTINCT n.colaborador) = 0 THEN 'Sem uso do computador no período escolhido.' "
             "ELSE 'Escolha um colaborador no filtro acima para ver o dia dele.' END AS \"Resumo\", "
             "CASE WHEN count(DISTINCT n.colaborador) = 1 THEN CASE WHEN " + PCT_PROD + " >= 60 THEN 'verde' "
             "WHEN " + PCT_PROD + " < 40 THEN 'amarelo' ELSE 'cinza' END ELSE 'azul' END AS \"Cor\" FROM n"),
     "viz": {}},
    {"name": "Uso ao longo do dia", "display": "custom:all-linha-do-tempo", "size": (24, 6), "use": "n",
     "description": "Em quais horas o computador foi usado e como (soma do período). Espaços vazios = sem uso.",
     "sql": ('SELECT n.hora AS "Hora", ' + TIPO + ' AS "Tipo", round(sum(n.seg_ativo) / 3600.0, 2) AS "Horas" '
             "FROM n WHERE n.categoria <> 'parado' GROUP BY 1, 2 ORDER BY 1"),
     "viz": {}},
    {"name": "Onde o tempo foi gasto", "display": "custom:all-ranking", "size": (12, 9), "use": "n",
     "description": "Programas e sites mais usados, com o tipo de cada um. Para mudar o tipo, fale com a ALL.",
     "sql": ('SELECT n.programa AS "Programa ou site", ' + TIPO + ' AS "Tipo", '
             'round(sum(n.seg_ativo) / 3600.0, 2) AS "Horas", ' + HM.format(m="sum(n.seg_ativo) / 60") + ' AS "Tempo" '
             "FROM n WHERE n.categoria <> 'parado' GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 12"),
     "viz": {}},
    {"name": "Telas capturadas", "display": "custom:all-galeria", "size": (12, 9), "use": "p",
     "description": "Imagens da tela do colaborador, uma a cada alguns minutos. Clique numa imagem para ampliar.",
     "sql": ('SELECT url AS "Tela", capturado_em AS "Quando", colaborador AS "Colaborador", '
             'programa AS "Programa ou site" FROM bi.prints '
             "WHERE cliente = '__ALL_WATCHER__' AND {{periodo}} "
             "[[AND colaborador = {{colaborador}}]] ORDER BY capturado_em DESC LIMIT 24"),
     "viz": {}},

    {"name": "Mapa da semana", "display": "custom:all-mapa-de-calor", "size": (24, 8), "use": "n", "click_colaborador": True,
     "description": ("Cada quadrado mostra a % do tempo trabalhando que foi em programas produtivos naquele dia da semana. "
                     "Clique no nome para ver só aquele colaborador."),
     "sql": ('SELECT n.colaborador AS "Colaborador", '
             + ", ".join(
                 "round(100.0 * sum(n.seg_ativo) FILTER (WHERE extract(isodow FROM n.dia) = %d AND n.categoria = 'produtivo') "
                 "/ NULLIF(sum(n.seg_ativo) FILTER (WHERE extract(isodow FROM n.dia) = %d), 0))::int AS \"%s\"" % (k, k, nome)
                 for k, nome in enumerate(DIAS_SEMANA, 1))
             + ", " + HM.format(m="sum(n.seg_ativo) / NULLIF(count(DISTINCT n.dia), 0) / 60")
             + ' AS "Tempo por dia" FROM n GROUP BY 1 ORDER BY 1'),
     "viz": {"all.verde_a_partir_de": 60, "all.amarelo_abaixo_de": 40, "all.sufixo": "%"}},
    {"name": "Computadores agora", "display": "custom:all-pessoas", "size": (12, 8), "use": "d",
     "description": "Quem está usando o computador neste momento. Atualiza sozinho.",
     "sql": ('SELECT d.colaborador AS "Colaborador", d.dispositivo AS "Computador", d.situacao AS "Situação", '
             'd.ultimo_contato AS "Último contato" FROM bi.dispositivos d '
             "WHERE d.cliente = '__ALL_WATCHER__' AND d.ativo "
             "ORDER BY CASE d.situacao WHEN 'Em uso' THEN 0 WHEN 'Sem contato hoje' THEN 1 ELSE 2 END, 1"),
     "viz": {}},
]


_POR_NOME = {c["name"]: c for c in CARDS}

# Sub-abas. "periodo" = filtro de datas da aba (chave em PERIODOS). Os cartoes de cada aba, na ordem.
TABS = [
    {"sub": "Visão geral", "periodo": "geral",
     "texto": ("**Como ler esta página.** Mostra como o tempo de trabalho foi usado no computador no período escolhido "
               "(padrão: hoje). **Produtivo** são os programas e sites do trabalho, **Neutro** são os de uso geral "
               "(navegador, mensagens) e **Fora do trabalho** são redes sociais, vídeos e jogos. O tempo em que o "
               "computador ficou parado não conta. Clique no cartão de um colaborador para ver só ele."),
     "cards": ["Colaboradores monitorados", "Tempo trabalhando por dia", "Tempo em programas produtivos",
               "Tempo fora do trabalho", "Como o tempo foi usado", "Colaboradores", "Pontos de atenção", "Dia a dia"]},
    {"sub": "Dia do colaborador", "periodo": "geral",
     "texto": ("**Um colaborador, um dia.** Escolha o colaborador (e o período) nos filtros acima. Abaixo ficam o resumo, "
               "as horas em que o computador foi usado, os programas e sites mais usados e as telas capturadas."),
     "cards": ["Resumo do dia", "Uso ao longo do dia", "Onde o tempo foi gasto", "Telas capturadas"]},
    {"sub": "Mapa da semana", "periodo": "semana",
     "texto": ("**Quem destoa aparece de relance.** O mapa mostra, por colaborador e dia da semana, a parte do tempo "
               "gasta em programas produtivos. Embaixo, os computadores da empresa agora e os programas mais usados pela equipe."),
     "cards": ["Mapa da semana", "Computadores agora", "Onde o tempo foi gasto"]},
]

# Filtros de periodo do painel: id, nome do filtro, padrao
PERIODOS = {"geral": {"id": "all_w_periodo", "slug": "periodo_atividade", "default": "thisday"},
            "semana": {"id": "all_w_periodo_semana", "slug": "periodo_semana", "default": "past7days~"}}
DIA_FIELD = {}  # preenchido em main(): {"atividade": id do campo bi.atividade.dia, "prints": id de bi.prints.dia}


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


CLIENTE_PADRAO = None  # definido em main(): cliente padrao do filtro do painel


def tags_for(sql, dia_field=None):
    """Variaveis do SQL. O cliente ganha valor padrao: sem ele o Metabase nao consegue calcular as colunas da
    pergunta ao salvar (o fork exige um cliente) e as listas de filtro viram caixa de texto. O periodo e um
    filtro de campo (data/todas as opcoes) sobre a coluna dia da tabela usada."""
    tags = {}
    for name in sorted(set(re.findall(r"\{\{\s*(\w+)\s*\}\}", sql))):
        if name == "periodo" and dia_field:
            tags[name] = {"id": "all-w-periodo", "name": name, "display-name": "Período", "type": "dimension",
                          "dimension": ["field", dia_field, None], "widget-type": "date/all-options"}
            continue
        tags[name] = {"id": f"all-w-{name}", "name": name, "type": "text",
                      "display-name": {"all_cliente": "Cliente", "colaborador": "Colaborador"}.get(name, name)}
        if name == "all_cliente" and CLIENTE_PADRAO:
            tags[name]["default"] = CLIENTE_PADRAO
    return tags


def card_params(tags):
    """Parametros do cartao (um por variavel), como o Metabase espera para ligar filtros e listas."""
    out = []
    for n, t in tags.items():
        if t["type"] == "dimension":
            out.append({"id": t["id"], "type": "date/all-options", "name": t["display-name"], "slug": n,
                        "target": ["dimension", ["template-tag", n]]})
        else:
            out.append({"id": t["id"], "type": "category", "name": t["display-name"], "slug": n,
                        "target": ["variable", ["template-tag", n]],
                        **({"default": t["default"]} if t.get("default") else {})})
    return out


def campo_dia(api, db_id):
    """Ids dos campos dia de bi.atividade e bi.prints."""
    meta = api.call("GET", f"/api/database/{db_id}/metadata")
    ids = {}
    for t in meta["tables"]:
        if t.get("schema") == "bi" and t["name"] in ("atividade", "prints"):
            for f in t["fields"]:
                if f["name"] == "dia":
                    ids[t["name"]] = f["id"]
    if len(ids) != 2:
        sys.exit("Nao achei bi.atividade.dia e bi.prints.dia no banco (rode a migracao 0004_bi.sql e sincronize o banco).")
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--painel", type=int, default=20)
    ap.add_argument("--banco", default="ALL Watcher")
    ap.add_argument("--grupo-demo", action="store_true")
    ap.add_argument("--cliente-padrao", default="Empresa Exemplo (demo)",
                    help="grupo de cliente (com codigo watcher) usado como padrao das perguntas; precisa existir, senao o Metabase nao calcula as colunas e as listas de filtro viram caixa de texto")
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
    if "cliente" not in param:
        sys.exit("O painel nao tem o filtro 'cliente'.")
    global CLIENTE_PADRAO
    CLIENTE_PADRAO = args.cliente_padrao
    DIA_FIELD.update(campo_dia(api, db["id"]))
    coll = next((dc["card"].get("collection_id") for dc in dash["dashcards"] if dc.get("card")), None)
    print(f"Painel: {dash['name']} - banco {db['name']} ({db['id']}) - pasta {coll}")
    for t in TABS:
        print(f"  {TAB_NAME}{SEP}{t['sub']}")
        for n in t["cards"]:
            print(f"     - {n} ({_POR_NOME[n]['display']})")
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
        "parameters": card_params(tags_for(lista_sql)),
        "dataset_query": {"database": db["id"], "type": "native",
                          "native": {"query": lista_sql, "template-tags": tags_for(lista_sql)}}})
    cliente = param["cliente"]
    colab = {"id": "all_colaborador", "name": "Colaborador", "slug": "colaborador", "type": "string/=",
             "sectionId": "string", "values_query_type": "list", "filteringParameters": [cliente["id"]],
             "values_source_type": "card",
             "values_source_config": {"card_id": lista["id"],
                                      "value_field": ["field", "Colaborador", {"base-type": "type/Text"}]}}
    periodos = [{"id": v["id"], "name": "Período", "slug": v["slug"], "type": "date/all-options",
                 "sectionId": "date", "default": v["default"]} for v in PERIODOS.values()]
    meus = {"colaborador"} | {v["slug"] for v in PERIODOS.values()}
    params = [p for p in dash["parameters"] if p["slug"] not in meus] + [colab] + periodos

    # abas: remove as antigas de monitoramento (e suas perguntas) e cria as tres sub-abas
    antigas = [t for t in dash["tabs"] if re.search(r"monitora", t["name"], re.I)]
    antigas_ids = {t["id"] for t in antigas}
    keep = [dc for dc in dash["dashcards"] if dc.get("dashboard_tab_id") not in antigas_ids]
    for dc in dash["dashcards"]:
        if dc.get("dashboard_tab_id") in antigas_ids and dc.get("card_id"):
            api.call("PUT", f"/api/card/{dc['card_id']}", {"archived": True})
    tabs = [{"id": t["id"], "name": t["name"]} for t in dash["tabs"] if t["id"] not in antigas_ids]

    new, next_id = [], [-1]
    for ti, tab in enumerate(TABS):
        tab_id = -(ti + 1)
        tabs.append({"id": tab_id, "name": f"{TAB_NAME}{SEP}{tab['sub']}"})
        per = PERIODOS[tab["periodo"]]
        next_id[0] -= 1
        new.append({
            "id": next_id[0], "card_id": None, "dashboard_tab_id": tab_id, "row": 0, "col": 0, "size_x": 24, "size_y": 3,
            "parameter_mappings": [], "series": [],
            "visualization_settings": {
                "virtual_card": {"name": None, "display": "text", "visualization_settings": {},
                                 "dataset_query": {}, "archived": False},
                "text": tab["texto"]}})
        col, row, line_h = 0, 3, 0
        for nome in tab["cards"]:
            c = _POR_NOME[nome]
            w, h = c["size"]
            if col + w > 24:
                row, col, line_h = row + line_h, 0, 0
            sql = full_sql(c)
            dia = DIA_FIELD["prints" if "p" in c["use"] else "atividade"]
            viz = json.loads(json.dumps(c["viz"]))
            created = api.call("POST", "/api/card", {
                "name": c["name"], "display": c["display"], "collection_id": coll,
                "description": c.get("description"), "visualization_settings": viz,
                "parameters": card_params(tags_for(sql, dia)),
                "dataset_query": {"database": db["id"], "type": "native",
                                  "native": {"query": sql, "template-tags": tags_for(sql, dia)}}})
            used = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", sql))
            maps = [{"parameter_id": cliente["id"], "card_id": created["id"],
                     "target": ["variable", ["template-tag", CLIENT_TAG]]}]
            if "periodo" in used:
                maps.append({"parameter_id": per["id"], "card_id": created["id"],
                             "target": ["dimension", ["template-tag", "periodo"]]})
            if "colaborador" in used:
                maps.append({"parameter_id": colab["id"], "card_id": created["id"],
                             "target": ["variable", ["template-tag", "colaborador"]]})
            dviz = {}
            if c.get("click_colaborador"):
                dviz["column_settings"] = {'["name","Colaborador"]': {"click_behavior": {
                    "type": "crossfilter", "parameterMapping": {colab["id"]: {
                        "id": colab["id"], "source": {"type": "column", "id": "Colaborador", "name": "Colaborador"},
                        "target": {"type": "parameter", "id": colab["id"]}}}}}}
            next_id[0] -= 1
            new.append({"id": next_id[0], "card_id": created["id"], "dashboard_tab_id": tab_id,
                        "row": row, "col": col, "size_x": w, "size_y": h,
                        "visualization_settings": dviz, "series": [], "parameter_mappings": maps})
            print(f"  + {tab['sub']}: pergunta {created['id']}: {c['name']}")
            col += w
            line_h = max(line_h, h)

    keep_cards = [{k: dc.get(k) for k in ("id", "card_id", "dashboard_tab_id", "row", "col", "size_x", "size_y",
                                          "parameter_mappings", "visualization_settings", "series")} for dc in keep]
    api.call("PUT", f"/api/dashboard/{args.painel}", {"parameters": params, "tabs": tabs, "dashcards": keep_cards + new})
    print(f"{len(TABS)} sub-abas de '{TAB_NAME}' criadas.")

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
