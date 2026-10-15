#!/usr/bin/env python3
"""
ALL Tecnologias — aba "Histórico de navegação" com DADOS FICTÍCIOS para demonstração.

Cria 8 perguntas e um aviso na aba cujo nome contém "navega" do painel modelo. Os dados são gerados na
própria consulta (generate_series + hashtext), sem tabela nenhuma: nada é gravado em banco algum.
Cada cliente vê números diferentes, porque a geração usa o código Squid do cliente (__ALL_SQUID__) como
semente. Por usar __ALL_SQUID__, a aba obedece ao interruptor "Histórico de Navegação" do grupo:
desligado, o cliente vê a prévia desfocada com o convite; a equipe vê os dados sempre.

Quando o Squid real estiver pronto, basta trocar o SQL das perguntas pela consulta nos logs.

Uso:
  export MB_URL=http://localhost:3002 MB_KEY=mb_...
  python3 bin/all-navegacao-demo.py                 # mostra o plano
  python3 bin/all-navegacao-demo.py --aplicar       # cria as perguntas e coloca na aba
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

CLIENT_TAG = "all_cliente"

BASE = """WITH p AS (SELECT '__ALL_SQUID__'::text AS cli),
u AS (SELECT * FROM (VALUES
  (1,'ana.souza','ESTACAO02','Financeiro'),(2,'bruno.lima','ESTACAO04','Comercial'),
  (3,'carla.mendes','ESTACAO06','Compras'),(4,'diego.rocha','ESTACAO07','Logística'),
  (5,'elisa.prado','ESTACAO09','RH'),(6,'fabio.nunes','ESTACAO11','Comercial'),
  (7,'gabriela.reis','ESTACAO13','Financeiro'),(8,'henrique.alves','ESTACAO15','Produção'),
  (9,'isabela.costa','ESTACAO17','Diretoria'),(10,'joao.martins','ESTACAO19','Logística'),
  (11,'karen.dias','ESTACAO21','Qualidade'),(12,'lucas.ferraz','ESTACAO24','TI')
) t(i, usuario, estacao, setor)),
s AS (SELECT * FROM (VALUES
  (1,'portal.empresa.com.br','Trabalho',false),(2,'mail.google.com','E-mail',false),
  (3,'outlook.office.com','E-mail',false),(4,'www.bb.com.br','Bancos',false),
  (5,'nfe.fazenda.gov.br','Governo',false),(6,'web.whatsapp.com','Comunicação',false),
  (7,'www.youtube.com','Vídeo e streaming',false),(8,'www.linkedin.com','Redes sociais',false),
  (9,'www.instagram.com','Redes sociais',false),(10,'g1.globo.com','Notícias',false),
  (11,'www.mercadolivre.com.br','Compras',false),(12,'open.spotify.com','Vídeo e streaming',false),
  (13,'www.facebook.com','Redes sociais',false),(14,'www.netflix.com','Vídeo e streaming',true),
  (15,'www.bet365.com','Apostas',true),(16,'store.steampowered.com','Jogos',true),
  (17,'www.twitch.tv','Jogos',true),(18,'nordvpn.com','Proxy e VPN',true)
) t(i, site, categoria, bloqueado)),
a AS (
  SELECT date_trunc('day', now() AT TIME ZONE 'America/Sao_Paulo')
           - ((abs(hashtext(p.cli || g || 'd')) % 7) * interval '1 day')
           + ((8 * 3600 + abs(hashtext(p.cli || g || 'h')) % (10 * 3600)) * interval '1 second') AS data_hora,
         1 + abs(hashtext(p.cli || g || 'u')) % 12 AS ui,
         1 + floor(18 * power((abs(hashtext(p.cli || g || 's')) % 1000) / 1000.0, 2.2))::int AS si,
         30 + abs(hashtext(p.cli || g || 't')) % 900 AS segundos
  FROM p, generate_series(1, 2000 + abs(hashtext((SELECT cli FROM p))) % 1500) g
),
n AS (
  SELECT a.data_hora, u.usuario, u.estacao, u.setor, s.site, s.categoria, s.bloqueado, a.segundos
  FROM a JOIN u ON u.i = a.ui JOIN s ON s.i = a.si
  WHERE a.data_hora <= now() AT TIME ZONE 'America/Sao_Paulo'
)
"""

DEMO = "DADOS FICTÍCIOS para demonstração do Histórico de Navegação (Squid/pfSense)."

GREEN, YELLOW, RED, BLUE = "#3CCB7F", "#F5BE4A", "#F26B6B", "#35A8E0"

CARDS = [
    {
        "name": "Acessos à internet (7 dias)", "display": "scalar", "size": (8, 3),
        "sql": 'SELECT count(*) AS "Acessos" FROM n',
        "viz": {},
    },
    {
        "name": "Acessos bloqueados (7 dias)", "display": "scalar", "size": (8, 3),
        "sql": 'SELECT count(*) AS "Bloqueados" FROM n WHERE n.bloqueado',
        "viz": {},
    },
    {
        "name": "Usuários navegando (7 dias)", "display": "scalar", "size": (8, 3),
        "sql": 'SELECT count(DISTINCT n.usuario) AS "Usuários" FROM n',
        "viz": {},
    },
    {
        "name": "Navegação por dia", "display": "bar", "size": (12, 7),
        "sql": """SELECT date_trunc('day', n.data_hora)::date AS "Dia",
       count(*) FILTER (WHERE NOT n.bloqueado) AS "Permitidos",
       count(*) FILTER (WHERE n.bloqueado) AS "Bloqueados"
FROM n GROUP BY 1 ORDER BY 1""",
        "viz": {
            "graph.dimensions": ["Dia"], "graph.metrics": ["Permitidos", "Bloqueados"],
            "stackable.stack_type": "stacked",
            "series_settings": {"Permitidos": {"color": BLUE}, "Bloqueados": {"color": RED}},
        },
    },
    {
        "name": "Sites mais acessados", "display": "row", "size": (12, 7),
        "sql": """SELECT n.site AS "Site", count(*) AS "Acessos"
FROM n WHERE NOT n.bloqueado GROUP BY 1 ORDER BY 2 DESC LIMIT 10""",
        "viz": {"graph.dimensions": ["Site"], "graph.metrics": ["Acessos"],
                "series_settings": {"Acessos": {"color": BLUE}}},
    },
    {
        "name": "Tempo por categoria (horas)", "display": "pie", "size": (8, 7),
        "sql": """SELECT n.categoria AS "Categoria", round(sum(n.segundos) / 3600.0, 1) AS "Horas"
FROM n WHERE NOT n.bloqueado GROUP BY 1 ORDER BY 2 DESC""",
        "viz": {"pie.dimension": "Categoria", "pie.metric": "Horas"},
    },
    {
        "name": "Navegação por usuário", "display": "table", "size": (16, 7),
        "sql": """SELECT n.usuario AS "Usuário", n.setor AS "Setor", n.estacao AS "Estação",
       count(*) AS "Acessos",
       round(sum(n.segundos) FILTER (WHERE NOT n.bloqueado) / 3600.0, 1) AS "Tempo (h)",
       count(*) FILTER (WHERE n.bloqueado) AS "Bloqueios"
FROM n GROUP BY 1, 2, 3 ORDER BY 6 DESC, 4 DESC""",
        "viz": {"table.column_formatting": [
            {"columns": ["Bloqueios"], "type": "single", "operator": ">=", "value": 40,
             "color": RED, "highlight_row": False},
            {"columns": ["Bloqueios"], "type": "single", "operator": ">=", "value": 20,
             "color": YELLOW, "highlight_row": False},
            {"columns": ["Bloqueios"], "type": "single", "operator": "<", "value": 20,
             "color": GREEN, "highlight_row": False},
        ]},
    },
    {
        "name": "Últimos acessos bloqueados", "display": "table", "size": (24, 8),
        "sql": """SELECT n.data_hora AS "Data e hora", n.usuario AS "Usuário", n.estacao AS "Estação",
       n.site AS "Site", n.categoria AS "Categoria", 'Bloqueado' AS "Situação"
FROM n WHERE n.bloqueado ORDER BY n.data_hora DESC LIMIT 100""",
        "viz": {"table.column_formatting": [
            {"columns": ["Situação"], "type": "single", "operator": "=", "value": "Bloqueado",
             "color": RED, "highlight_row": False},
        ]},
    },
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


def card_db_and_sql(card):
    dq = card.get("dataset_query") or {}
    if "stages" in dq:
        return dq.get("database"), dq["stages"][0].get("native") or ""
    return dq.get("database"), (dq.get("native") or {}).get("query") or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--painel", type=int, default=20)
    ap.add_argument("--grupo", default="Grupo Tecmar")
    ap.add_argument("--codigo-squid", default="tecmar")
    args = ap.parse_args()

    api = Api(os.environ.get("MB_URL", ""), os.environ.get("MB_KEY", ""))
    if not api.url or not api.key:
        sys.exit("Defina MB_URL e MB_KEY.")

    dash = api.call("GET", f"/api/dashboard/{args.painel}")
    tab = next((t for t in dash.get("tabs") or [] if re.search(r"navega", t["name"], re.I)), None)
    if not tab:
        sys.exit(f"O painel {dash['name']} não tem aba com 'navega' no nome.")
    param = next((p for p in dash.get("parameters") or [] if p.get("slug") == "cliente"), None)
    if not param:
        sys.exit("O painel não tem o filtro com slug 'cliente'.")

    # banco Postgres: o mesmo das perguntas da auditoria (Wazuh), só para rodar o generate_series
    db = coll = None
    for dc in dash["dashcards"]:
        card = dc.get("card") or {}
        if card.get("id"):
            card_db, sql = card_db_and_sql(card)
            if "__ALL_WAZUH__" in sql:
                db, coll = card_db, card.get("collection_id")
                break
    if db is None:
        sys.exit("Não achei uma pergunta da auditoria (__ALL_WAZUH__) no painel para saber o banco Postgres.")

    existing = [dc for dc in dash["dashcards"] if dc.get("dashboard_tab_id") == tab["id"]]
    print(f"Painel: {dash['name']} · aba '{tab['name']}' ({len(existing)} cartões hoje) · banco {db} · pasta {coll}")
    for c in CARDS:
        print(f"  - {c['name']} ({c['display']})")
    if not args.aplicar:
        print("\nNada foi criado. Rode com --aplicar.")
        return

    row0 = max([dc["row"] + dc["size_y"] for dc in existing] or [0])
    new = [{
        "id": -1, "card_id": None, "dashboard_tab_id": tab["id"],
        "row": row0, "col": 0, "size_x": 24, "size_y": 1,
        "parameter_mappings": [], "series": [],
        "visualization_settings": {
            "virtual_card": {"name": None, "display": "text", "visualization_settings": {},
                             "dataset_query": {}, "archived": False},
            "text": "**Demonstração:** os números desta aba são fictícios. Os dados reais virão do Squid/pfSense do cliente.",
        },
    }]
    col, row, line_h = 0, row0 + 1, 0
    for i, c in enumerate(CARDS):
        w, h = c["size"]
        if col + w > 24:
            row, col, line_h = row + line_h, 0, 0
        created = api.call("POST", "/api/card", {
            "name": c["name"], "display": c["display"], "collection_id": coll,
            "description": DEMO, "visualization_settings": c["viz"],
            "dataset_query": {"database": db, "type": "native", "native": {
                "query": BASE + c["sql"] + "\n/* {{" + CLIENT_TAG + "}} */",
                "template-tags": {CLIENT_TAG: {"id": f"all-cliente-nav-{i}", "name": CLIENT_TAG,
                                               "display-name": "Cliente", "type": "text"}},
            }},
        })
        print(f"  + pergunta {created['id']}: {c['name']}")
        new.append({
            "id": -(i + 2), "card_id": created["id"], "dashboard_tab_id": tab["id"],
            "row": row, "col": col, "size_x": w, "size_y": h,
            "visualization_settings": {}, "series": [],
            "parameter_mappings": [{"parameter_id": param["id"], "card_id": created["id"],
                                    "target": ["variable", ["template-tag", CLIENT_TAG]]}],
        })
        col += w
        line_h = max(line_h, h)

    keep = [{k: dc.get(k) for k in ("id", "card_id", "dashboard_tab_id", "row", "col", "size_x", "size_y",
                                    "parameter_mappings", "visualization_settings", "series")}
            for dc in dash["dashcards"]]
    api.call("PUT", f"/api/dashboard/{args.painel}", {
        "tabs": [{"id": t["id"], "name": t["name"]} for t in dash["tabs"]],
        "dashcards": keep + new,
    })
    print(f"Aba '{tab['name']}' preenchida.")

    groups = api.call("GET", "/api/permissions/group")
    group = next((g for g in groups if g["name"].strip().lower() == args.grupo.lower()), None)
    if group:
        config = api.call("GET", "/api/setting/all-client-group-config") or {}
        cfg = config.get(str(group["id"])) or {"codes": {}, "services": {}}
        cfg.setdefault("codes", {})["squid"] = cfg.get("codes", {}).get("squid") or args.codigo_squid
        config[str(group["id"])] = cfg
        api.call("PUT", "/api/setting/all-client-group-config", {"value": config})
        print(f"Código Squid do {args.grupo}: {cfg['codes']['squid']} · serviços: {cfg.get('services')}")


if __name__ == "__main__":
    main()
