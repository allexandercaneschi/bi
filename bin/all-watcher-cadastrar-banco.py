#!/usr/bin/env python3
"""Cadastra o banco "ALL Watcher" no Metabase de teste, lendo a conexao do .env da API (sem mostrar a senha).

  export MB_URL=http://localhost:3002 MB_KEY=mb_...
  python3 cadastrar-banco.py [--env /opt/all-watcher/.env] [--usuario watcher_bi --senha ...]

Por padrao usa o mesmo usuario da API (DATABASE_URL). Depois troque por watcher_bi (somente leitura).
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--env", default="/opt/all-watcher/.env")
ap.add_argument("--nome", default="ALL Watcher")
ap.add_argument("--usuario")
ap.add_argument("--senha")
a = ap.parse_args()

url = os.environ.get("MB_URL", "").rstrip("/")
key = os.environ.get("MB_KEY", "")
if not url or not key:
    sys.exit("Defina MB_URL e MB_KEY.")

dsn = next((l.split("=", 1)[1].strip() for l in open(a.env, encoding="utf-8") if l.startswith("DATABASE_URL=")), None)
if not dsn:
    sys.exit("DATABASE_URL nao encontrada em " + a.env)
u = urllib.parse.urlparse(dsn)


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url + path, data=data, method=method,
                                 headers={"x-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        sys.exit(f"Erro {e.code} em {method} {path}: {e.read().decode(errors='replace')[:400]}")


dbs = call("GET", "/api/database")
dbs = dbs["data"] if isinstance(dbs, dict) else dbs
ex = next((d for d in dbs if d["name"] == a.nome), None)
details = {"host": u.hostname, "port": u.port or 5432, "dbname": u.path.lstrip("/"),
           "user": a.usuario or urllib.parse.unquote(u.username or ""),
           "password": a.senha or urllib.parse.unquote(u.password or ""),
           "ssl": False, "tunnel-enabled": False}
if ex:
    call("PUT", f"/api/database/{ex['id']}", {"details": details})
    print(f"Banco '{a.nome}' ja existia (id {ex['id']}): conexao atualizada para o usuario {details['user']}.")
else:
    c = call("POST", "/api/database", {"name": a.nome, "engine": "postgres", "details": details,
                                       "is_full_sync": True, "auto_run_queries": True})
    print(f"Banco '{a.nome}' criado (id {c['id']}) com o usuario {details['user']}.")
