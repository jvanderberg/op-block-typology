"""Provenance recording shared by every stage.

Each stage opens a Stage(...) context. Every file it reads is registered as an
input (path + sha256 + size); every file it writes is registered as an output
(path + sha256 + size + row count where applicable). Parameters used and
free-text notes are logged. On close the record is written to
outputs/provenance/<stage>.json and the notes are appended to
outputs/audit.log. s09_provenance.py later verifies that every input hash
matches the output hash of the stage that produced it, so the lineage of every
number in outputs/ can be traced back to a fetched upstream file or the
fingerprinted source database.
"""
import hashlib
import json
import os
import platform
import sys
import time

from config import AUDIT_PATH, PROV_DIR, ROOT


def sha256_file(path, limit=None):
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            if limit is not None and n + len(chunk) > limit:
                chunk = chunk[: limit - n]
            h.update(chunk)
            n += len(chunk)
            if limit is not None and n >= limit:
                break
    return h.hexdigest()


def rel(path):
    path = os.path.abspath(path)
    return os.path.relpath(path, ROOT) if path.startswith(ROOT) else path


def count_rows(path):
    """Row count for CSV (data rows), JSON lists, GeoJSON feature collections."""
    try:
        if path.endswith(".csv"):
            with open(path, "rb") as f:
                return max(0, sum(1 for _ in f) - 1)
        if path.endswith(".geojson"):
            with open(path) as f:
                return len(json.load(f).get("features", []))
        if path.endswith(".json"):
            with open(path) as f:
                obj = json.load(f)
            if isinstance(obj, list):
                return len(obj)
            if isinstance(obj, dict) and "data" in obj and isinstance(obj["data"], dict):
                return len(obj["data"])
    except Exception:  # noqa: BLE001 - counting is best-effort metadata
        return None
    return None


class Stage:
    def __init__(self, name, script):
        self.name = name
        self.script = script
        self.started = time.time()
        self.rec = {
            "stage": name,
            "script": rel(script),
            "script_sha256": sha256_file(script),
            "config_sha256": sha256_file(os.path.join(ROOT, "config.py")),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started)),
            "params": {},
            "inputs": [],
            "outputs": [],
            "notes": [],
        }
        os.makedirs(PROV_DIR, exist_ok=True)
        self.note(f"start {self.rec['script']} (sha256 {self.rec['script_sha256'][:12]})")

    # -- recording -------------------------------------------------------
    def param(self, **kw):
        for k, v in kw.items():
            self.rec["params"][k] = v
            self.note(f"param {k}={v!r}")

    def input(self, path, role="", partial_hash=None, extra=None):
        d = {"path": rel(path), "role": role, "bytes": os.path.getsize(path)}
        if partial_hash:
            d["sha256_first_bytes"] = partial_hash
            d["sha256_partial"] = sha256_file(path, partial_hash)
        else:
            d["sha256"] = sha256_file(path)
        if extra:
            d.update(extra)
        self.rec["inputs"].append(d)
        h = d.get("sha256") or d.get("sha256_partial")
        self.note(f"input  {d['path']} ({role}) sha256={h[:12]} bytes={d['bytes']}")
        return d

    def output(self, path, role="", extra=None):
        d = {"path": rel(path), "role": role, "bytes": os.path.getsize(path),
             "sha256": sha256_file(path), "rows": count_rows(path)}
        if extra:
            d.update(extra)
        self.rec["outputs"].append(d)
        self.note(f"output {d['path']} ({role}) sha256={d['sha256'][:12]} rows={d['rows']}")
        return d

    def note(self, msg):
        line = f"[{self.name}] {msg}"
        print(line, flush=True)
        self.rec["notes"].append(msg)
        with open(AUDIT_PATH, "a") as f:
            f.write(line + "\n")

    # -- context ---------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.rec["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.rec["seconds"] = round(time.time() - self.started, 1)
        self.rec["ok"] = exc is None
        if exc is not None:
            self.note(f"FAILED: {exc_type.__name__}: {exc}")
        path = os.path.join(PROV_DIR, f"{self.name}.json")
        with open(path, "w") as f:
            json.dump(self.rec, f, indent=1, sort_keys=True)
        self.note(f"end ({self.rec['seconds']}s) -> {rel(path)}")
        return False
