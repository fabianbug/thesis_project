from pathlib import Path
import json, csv, re

_CTRL = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')  # verbotene Steuerzeichen


def read_jsonl(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                # einmal versuchen zu reparieren (Steuerzeichen raus)
                fixed = _CTRL.sub(" ", line)
                try:
                    yield json.loads(fixed)
                except json.JSONDecodeError:
                    raise ValueError(f"{path}:{lineno}: invalid JSONL ({e})\nLine: {line[:200]!r}")

def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
