#!/usr/bin/env python3
"""
ALL Tecnologias — publica o painel modelo do Metabase de teste na produção (ou atualiza o que já foi publicado).

Copia o painel, as perguntas dele e as perguntas "Lista · ..." usadas nos filtros em dropdown, trocando os ids das
perguntas pelos ids da produção. Só usa a API do Metabase; não toca nos bancos dos sistemas (ERP, Zabbix, etc.).
Os ids dos bancos de dados são os mesmos nos dois Metabase (o de teste é cópia da produção).

Atualização: rodando de novo, as perguntas são casadas pelo nome dentro da pasta de destino e atualizadas no lugar;
o painel é casado pelo nome e atualizado (as abas são casadas pelo nome, então os links continuam valendo).

  MB_SRC_URL=http://localhost:3002 MB_SRC_KEY=<chave do teste> \\
  MB_URL=http://localhost:3000     MB_KEY=<chave da produção> \\
  python3 all-publicar-painel.py [--painel 20] [--grupos] [--aplicar]

  --grupos   também copia a configuração dos grupos de cliente (códigos e serviços) do teste para a produção
  --aplicar  sem isso, só mostra o que seria feito
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

CARD_FIELDS = ("name", "description", "display", "visualization_settings", "dataset_query", "parameters", "type")


class Api:
    def __init__(self, url, key):
        self.url, self.key = url.rstrip("/"), key

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.url + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"x-api-key": self.key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            sys.exit(f"Erro {e.code} em {method} {self.url}{path}: {e.read().decode(errors='replace')[:500]}")


def source_card_ids(params):
    for p in params or []:
        cfg = p.get("values_source_config") or {}
        if p.get("values_source_type") == "card" and cfg.get("card_id"):
            yield cfg["card_id"]


def remap_params(params, idmap):
    out = []
    for p in params or []:
        p = json.loads(json.dumps(p))
        cfg = p.get("values_source_config") or {}
        if p.get("values_source_type") == "card" and cfg.get("card_id"):
            cfg["card_id"] = idmap[cfg["card_id"]]
        out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--painel", type=int, default=20, help="id do painel no Metabase de teste")
    ap.add_argument("--grupos", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()
    for v in ("MB_SRC_URL", "MB_SRC_KEY", "MB_URL", "MB_KEY"):
        if not os.environ.get(v):
            sys.exit("Defina MB_SRC_URL e MB_SRC_KEY (teste) e MB_URL e MB_KEY (produção).")
    src = Api(os.environ["MB_SRC_URL"], os.environ["MB_SRC_KEY"])
    dst = Api(os.environ["MB_URL"], os.environ["MB_KEY"])
    if src.url == dst.url:
        sys.exit("Origem e destino são o mesmo Metabase.")

    # ---- origem: painel, perguntas do painel e listas usadas pelos filtros
    dash = src.call("GET", f"/api/dashboard/{args.painel}")
    coll = src.call("GET", f"/api/collection/{dash['collection_id']}")
    cards, todo = {}, [dc["card_id"] for dc in dash["dashcards"] if dc.get("card_id")]
    todo += list(source_card_ids(dash.get("parameters")))
    while todo:
        cid = todo.pop()
        if cid in cards:
            continue
        cards[cid] = src.call("GET", f"/api/card/{cid}")
        todo += list(source_card_ids(cards[cid].get("parameters")))
    names = [c["name"] for c in cards.values()]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        sys.exit(f"Perguntas com nome repetido na origem (renomeie antes): {sorted(dup)}")
    print(f"Origem: painel \"{dash['name']}\" na pasta \"{coll['name']}\": "
          f"{len(dash.get('tabs') or [])} abas, {len(dash['parameters'])} filtros, {len(cards)} perguntas")

    # ---- destino: pasta, perguntas e painel com o mesmo nome (se já publicado)
    dcoll = next((c for c in dst.call("GET", "/api/collection")
                  if c.get("name") == coll["name"] and not c.get("archived") and c.get("location") == "/"), None)
    existing, ddash = {}, None
    if dcoll:
        for it in dst.call("GET", f"/api/collection/{dcoll['id']}/items?models=card&models=dashboard")["data"]:
            if it["model"] == "card":
                existing[it["name"]] = it["id"]
            elif it["name"] == dash["name"]:
                ddash = it["id"]
    novas = [n for n in names if n not in existing]
    print(f"Destino: pasta {'existente (id %s)' % dcoll['id'] if dcoll else 'nova'}, "
          f"{len(names) - len(novas)} perguntas a atualizar, {len(novas)} a criar, "
          f"painel {'existente (id %s), será atualizado' % ddash if ddash else 'novo'}")
    for n in novas:
        print(f"  + {n}")

    if args.grupos:
        gids = src.call("GET", "/api/setting/all-client-group-ids") or []
        gcfg = src.call("GET", "/api/setting/all-client-group-config") or {}
        sg = {g["id"]: g["name"] for g in src.call("GET", "/api/permissions/group")}
        dg = {g["id"]: g["name"] for g in dst.call("GET", "/api/permissions/group")}
        for gid in gids:
            if dg.get(gid) != sg.get(gid):
                sys.exit(f"Grupo {gid} tem nome diferente: teste \"{sg.get(gid)}\", produção \"{dg.get(gid)}\". "
                         "Configure os grupos à mão em Admin → Pessoas → Grupos.")
        print(f"Grupos de cliente a copiar: {', '.join(sg[g] for g in gids)}")

    if not args.aplicar:
        print("\nNada foi alterado. Rode com --aplicar.")
        return

    if not dcoll:
        dcoll = dst.call("POST", "/api/collection", {"name": coll["name"], "parent_id": None,
                                                     "description": coll.get("description")})
        print(f"Pasta criada: {dcoll['name']} (id {dcoll['id']})")

    # 1) cria/atualiza as perguntas sem os filtros (os filtros podem apontar para listas ainda não criadas)
    idmap = {}
    for cid, c in cards.items():
        body = {k: c.get(k) for k in CARD_FIELDS if k != "parameters"}
        body["collection_id"] = dcoll["id"]
        if c["name"] in existing:
            idmap[cid] = existing[c["name"]]
            dst.call("PUT", f"/api/card/{idmap[cid]}", body)
        else:
            idmap[cid] = dst.call("POST", "/api/card", body)["id"]
    # 2) filtros das perguntas, com as listas já com os ids da produção
    for cid, c in cards.items():
        if c.get("parameters"):
            dst.call("PUT", f"/api/card/{idmap[cid]}", {"parameters": remap_params(c["parameters"], idmap)})
    print(f"{len(cards)} perguntas publicadas")

    # 3) painel
    if not ddash:
        ddash = dst.call("POST", "/api/dashboard", {"name": dash["name"], "collection_id": dcoll["id"],
                                                    "description": dash.get("description")})["id"]
    old_tabs = {t["name"]: t["id"] for t in (dst.call("GET", f"/api/dashboard/{ddash}").get("tabs") or [])}
    tab_ids = {}
    for i, t in enumerate(dash.get("tabs") or []):
        tab_ids[t["id"]] = old_tabs.get(t["name"], -(i + 1))
    dashcards = []
    for i, dc in enumerate(dash["dashcards"]):
        dashcards.append({
            "id": -(i + 1),
            "card_id": idmap.get(dc.get("card_id")),
            "dashboard_tab_id": tab_ids.get(dc.get("dashboard_tab_id")),
            "row": dc["row"], "col": dc["col"], "size_x": dc["size_x"], "size_y": dc["size_y"],
            "visualization_settings": dc.get("visualization_settings") or {},
            "series": [],
            "parameter_mappings": [dict(m, card_id=idmap[m["card_id"]]) for m in dc.get("parameter_mappings") or []
                                   if m.get("card_id") in idmap],
        })
    dst.call("PUT", f"/api/dashboard/{ddash}", {
        "name": dash["name"], "description": dash.get("description"), "width": dash.get("width", "full"),
        "tabs": [{"id": tab_ids[t["id"]], "name": t["name"]} for t in (dash.get("tabs") or [])],
        "parameters": remap_params(dash["parameters"], idmap),
        "dashcards": dashcards,
    })
    print(f"Painel publicado: {dst.url}/dashboard/{ddash}")

    if args.grupos:
        dids = dst.call("GET", "/api/setting/all-client-group-ids") or []
        dcfg = dst.call("GET", "/api/setting/all-client-group-config") or {}
        dst.call("PUT", "/api/setting/all-client-group-ids", {"value": sorted(set(dids) | set(gids))})
        dcfg.update({str(g): gcfg[str(g)] for g in gids if str(g) in gcfg})
        dst.call("PUT", "/api/setting/all-client-group-config", {"value": dcfg})
        print("Configuração dos grupos de cliente copiada")


if __name__ == "__main__":
    main()
