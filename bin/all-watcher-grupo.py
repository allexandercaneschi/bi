#!/usr/bin/env python3
"""Cria (ou atualiza) um grupo de cliente no Metabase de teste com o codigo do ALL Watcher.
  MB_URL=... MB_KEY=... python3 grupo.py "Nome do grupo" slug-do-cliente"""
import json
import os
import sys
import urllib.error
import urllib.request

url, key = os.environ["MB_URL"].rstrip("/"), os.environ["MB_KEY"]
nome, slug = sys.argv[1], sys.argv[2]


def call(method, path, body=None):
    req = urllib.request.Request(url + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers={"x-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        sys.exit(f"Erro {e.code} em {method} {path}: {e.read().decode(errors='replace')[:300]}")


groups = call("GET", "/api/permissions/group")
g = next((x for x in groups if x["name"] == nome), None) or call("POST", "/api/permissions/group", {"name": nome})
ids = call("GET", "/api/setting/all-client-group-ids") or []
if g["id"] not in ids:
    call("PUT", "/api/setting/all-client-group-ids", {"value": ids + [g["id"]]})
cfg_all = call("GET", "/api/setting/all-client-group-config") or {}
cfg = cfg_all.get(str(g["id"])) or {"codes": {}, "services": {}}
cfg.setdefault("codes", {})["watcher"] = slug
cfg.setdefault("services", {})["monitoramento"] = True
cfg_all[str(g["id"])] = cfg
call("PUT", "/api/setting/all-client-group-config", {"value": cfg_all})
print(f"Grupo '{nome}' (id {g['id']}): watcher = {slug}, monitoramento ligado.")
