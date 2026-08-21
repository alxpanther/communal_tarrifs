"""Замер облачного распознавания счётчиков на реальных фотографиях.

Гоняет один и тот же набор снимков через несколько моделей разных провайдеров
и складывает сырые ответы в JSON. Сравнение с эталоном — отдельным шагом.
"""

import base64, json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.expanduser("~/AndroidStudioProjects/kommeter")
ENV = os.path.expanduser("~/AndroidStudioProjects/kommeter_scripts/.env")

env = {}
for line in open(ENV):
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

QWEN = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
ZAI = "https://api.z.ai/api/paas/v4"
OR = "https://openrouter.ai/api/v1"

# provider, base url, key, model id
TARGETS = [
    ("qwen",   QWEN, env["QWEN_API_KEY"],       "qwen-vl-max"),
    ("qwen",   QWEN, env["QWEN_API_KEY"],       "qwen3-vl-plus"),
    ("zai",    ZAI,  env["GLM_API_KEY"],        "glm-4.6v"),
    ("or",     OR,   env["OPENROUTER_API_KEY"], "google/gemini-3.7-flash"),
]

DRUM = ("На фотографии барабанный счётчик воды: пять чёрных барабанов (целая часть) "
        "и три красных (доли). Прочитай показание. Ответь только JSON без пояснений: "
        '{"integer":"<пять цифр целой части>","fraction":"<три цифры долей>","confidence":<0..1>}')

DIGITAL = ("На фотографии электронный счётчик с семисегментным табло. Прочитай показание "
           "целиком, как оно написано на табло. Ответь только JSON без пояснений: "
           '{"reading":"<цифры табло, разделитель точкой если он есть>","confidence":<0..1>}')


def ask(base, key, model, prompt, photo, retries=2):
    b64 = base64.b64encode(open(photo, "rb").read()).decode()
    body = {"model": model, "temperature": 0, "max_tokens": 3000,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}]}
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    for attempt in range(retries + 1):
        started = time.time()
        try:
            r = json.load(urllib.request.urlopen(req, timeout=180))
            msg = r["choices"][0]["message"]
            usage = r.get("usage", {})
            return {"text": msg.get("content") or "", "seconds": round(time.time() - started, 1),
                    "in": usage.get("prompt_tokens"), "out": usage.get("completion_tokens"),
                    "think": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")}
        except Exception as e:
            detail = e.read().decode()[:200] if hasattr(e, "read") else str(e)[:200]
            if attempt == retries:
                return {"error": f"{type(e).__name__}: {detail}"}
            time.sleep(3 * (attempt + 1))


def photos(folder):
    path = f"{ROOT}/docs/{folder}"
    return [f"{path}/{n}" for n in sorted(os.listdir(path)) if n.endswith(".jpg")]


def main():
    jobs = []
    for kind, folder, prompt in (("drum", "drum_scoreboard", DRUM),
                                 ("digital", "digital_scoreboard", DIGITAL)):
        for photo in photos(folder):
            for provider, base, key, model in TARGETS:
                jobs.append((kind, photo, provider, base, key, model, prompt))

    results = []
    done = [0]

    def run(job):
        kind, photo, provider, base, key, model, prompt = job
        answer = ask(base, key, model, prompt, photo)
        done[0] += 1
        print(f"{done[0]:3}/{len(jobs)} {model:26} {os.path.basename(photo):34} "
              f"{answer.get('text', answer.get('error', ''))[:60]!r}", flush=True)
        return {"kind": kind, "photo": os.path.basename(photo), "provider": provider,
                "model": model, **answer}

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(run, jobs))

    out = f"{os.path.dirname(ENV)}/ocr_benchmark_raw.json"
    json.dump(results, open(out, "w"), ensure_ascii=False, indent=1)
    print("записано:", out)


if __name__ == "__main__":
    main()
