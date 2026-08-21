"""Сводка по замеру: таблица «снимок × модель», согласие моделей, токены и цена."""

import json, os, re, sys
from collections import defaultdict

RAW = os.path.expanduser("~/AndroidStudioProjects/kommeter_scripts/ocr_benchmark_raw.json")

# цена за миллион токенов: вход, выход
PRICES = {
    "qwen-vl-max": (0.80, 3.20),
    "qwen3-vl-plus": (0.21, 1.90),
    "glm-4.6v": (0.30, 0.90),
    "google/gemini-3.7-flash": (0.375, 1.875),
}


def value_of(row):
    """Показание из ответа модели: целая часть для барабанов, всё табло для электронных."""
    text = row.get("text") or ""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if row["kind"] == "drum":
        got = data.get("integer")
    else:
        got = data.get("reading")
    return str(got).strip() if got is not None else None


def main():
    rows = json.load(open(RAW))
    models = sorted({r["model"] for r in rows})
    by_photo = defaultdict(dict)
    for r in rows:
        by_photo[(r["kind"], r["photo"])][r["model"]] = r

    for kind in ("drum", "digital"):
        photos = sorted(p for k, p in by_photo if k == kind)
        print(f"\n=== {'БАРАБАННЫЕ' if kind == 'drum' else 'ЭЛЕКТРОННЫЕ'} ({len(photos)} снимков) ===")
        head = f"{'снимок':34}" + "".join(f"{m[:22]:24}" for m in models) + "согласие"
        print(head)
        agree = defaultdict(int)
        for photo in photos:
            cells = []
            values = []
            for m in models:
                row = by_photo[(kind, photo)].get(m, {})
                v = value_of(row) if row else None
                cells.append(v if v else ("ОШИБКА" if row.get("error") else "—"))
                values.append(v)
            same = len({v for v in values if v}) == 1 and all(values)
            for m, v in zip(models, values):
                if same and v:
                    agree[m] += 1
            print(f"{photo[:33]:34}" + "".join(f"{c:24}" for c in cells) + ("все совпали" if same else "РАСХОЖДЕНИЕ"))

    print("\n=== токены, время и цена за снимок ===")
    for m in models:
        rs = [r for r in rows if r["model"] == m and not r.get("error")]
        if not rs:
            print(f"{m:26} все запросы с ошибкой")
            continue
        tin = sum(r["in"] for r in rs) / len(rs)
        tout = sum(r["out"] for r in rs) / len(rs)
        think = sum(r.get("think") or 0 for r in rs) / len(rs)
        secs = sum(r["seconds"] for r in rs) / len(rs)
        pin, pout = PRICES.get(m, (0, 0))
        cost = tin / 1e6 * pin + tout / 1e6 * pout
        errors = len([r for r in rows if r["model"] == m and r.get("error")])
        print(f"{m:26} вход {tin:6.0f}  выход {tout:5.0f} (из них размышления {think:4.0f})  "
              f"{secs:4.1f}с  ${cost:.5f}/снимок  ошибок: {errors}")


if __name__ == "__main__":
    main()
