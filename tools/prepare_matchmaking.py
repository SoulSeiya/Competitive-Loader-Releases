"""Download a pinned upstream Worker for deployment, with its source and licence.

Does not log in, provision resources, set secrets or deploy anything.
"""
import hashlib
import json
from pathlib import Path
import urllib.request

REF="5b0ad7ed1513fd99de6d4bdd2719c917acbf672e"
BASE=f"https://raw.githubusercontent.com/z3xox/Tenkaichi3Decomp/{REF}/"
DESTINATION=Path(__file__).resolve().parents[1]/"service"/"cloudflare-matchmaking"/"upstream"


def main():
    DESTINATION.mkdir(parents=True,exist_ok=True)
    manifest={"repository":"https://github.com/z3xox/Tenkaichi3Decomp","commit":REF,"files":{}}
    for name in ("worker.js","schema.sql","README.md","test.mjs","LICENSE"):
        source=name if name=="LICENSE" else "port/matchmaking/"+name
        request=urllib.request.Request(BASE+source,headers={"User-Agent":"BTC-Loader-deployment-preparation"})
        with urllib.request.urlopen(request,timeout=30) as response:
            data=response.read(2_000_001)
        if len(data)>2_000_000:raise ValueError("Unexpected upstream file size")
        (DESTINATION/name).write_bytes(data)
        manifest["files"][name]=hashlib.sha256(data).hexdigest()
    (DESTINATION/"source.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print(f"Worker pinned at {REF}; deployment files: {DESTINATION}")


if __name__=="__main__":main()
