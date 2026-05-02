"""Extract all FastAPI routes from the running app via OpenAPI spec."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from app.main import app

openapi = app.openapi()
paths = openapi.get("paths", {})

print(f"Total endpoints: {sum(len(v) for v in paths.values())}\n")
for path in sorted(paths.keys()):
    methods = paths[path]
    for method, details in methods.items():
        summary = details.get("summary", "")
        tags = details.get("tags", [])
        print(f"{method.upper():7s} {path:60s} [{', '.join(tags)}] {summary}")
