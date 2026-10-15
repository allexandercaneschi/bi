#!/usr/bin/env python3
"""
ALL Tecnologias — testa o painel modelo com os filtros: roda cada pergunta (como a equipe, cliente do filtro
"Cliente") sem filtros, com datas e com o primeiro valor de cada lista. Mostra só os erros e um resumo.

  MB_URL=http://localhost:3002 MB_KEY=... python3 all-testa-filtros.py [--painel 20] [--cliente Tecmar]
"""
import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--painel", type=int, default=20)
    ap.add_argument("--cliente", default="Tecmar")
    args = ap.parse_args()
    url, key = os.environ["MB_URL"].rstrip("/"), os.environ["MB_KEY"]

    def api(method, path, body=None):
        req = urllib.request.Request(url + path, data=json.dumps(body).encode() if body is not None else None,
                                     method=method, headers={"x-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            return {"status": "http", "error": e.read().decode(errors="replace")[:300]}

    d = api("GET", f"/api/dashboard/{args.painel}")
    tabs = {t["id"]: t["name"] for t in d["tabs"]}
    params = {p["id"]: p for p in d["parameters"]}
    cliente = next(p for p in d["parameters"] if p["slug"] == "cliente")

    # listas: primeiro valor de cada filtro em lista (testa também as perguntas "Lista · ...")
    first = {}
    for pid, p in params.items():
        if p.get("values_query_type") == "list" and p["slug"] != "cliente":
            q = urllib.parse.urlencode({cliente["id"]: args.cliente})
            r = api("GET", f"/api/dashboard/{args.painel}/params/{pid}/values?{q}")
            vals = (r or {}).get("values") if isinstance(r, dict) else None
            if vals:
                v = vals[0][0] if isinstance(vals[0], list) else vals[0]
                first[pid] = v
                print(f"lista {p['name']} ({p['slug']}): {len(vals)} itens, ex.: {v}")
            else:
                print(f"LISTA VAZIA OU ERRO {p['name']} ({p['slug']}): {str(r)[:200]}")

    def run(label, extra):
        ok = bad = 0
        for dc in d["dashcards"]:
            c = dc.get("card") or {}
            if not c.get("id") or not dc.get("parameter_mappings"):
                continue
            mapped = {m["parameter_id"] for m in dc["parameter_mappings"]}
            ps = [{"id": cliente["id"], "type": cliente["type"], "value": [args.cliente]}]
            for pid, val in extra(mapped):
                ps.append({"id": pid, "type": params[pid]["type"], "value": val})
            r = api("POST", f"/api/dashboard/{args.painel}/dashcard/{dc['id']}/card/{c['id']}/query", {"parameters": ps})
            if r.get("status") == "completed":
                ok += 1
            else:
                bad += 1
                print(f"  ERRO [{label}] {tabs.get(dc['dashboard_tab_id'])} | {c['name']} | {str(r.get('error'))[:220]}")
        print(f"{label}: {ok} ok, {bad} com erro")

    by_slug = {p["slug"]: pid for pid, p in params.items()}
    run("sem filtros", lambda m: [])
    run("com datas 01/07 a 30/09", lambda m: [(by_slug[s], v) for s, v in
                                               (("data_inicial", "2026-07-01"), ("data_final", "2026-09-30"))
                                               if by_slug.get(s) in m])
    run("com listas (1º valor)", lambda m: [(pid, [v]) for pid, v in first.items() if pid in m])


if __name__ == "__main__":
    main()
