#!/usr/bin/env python3
"""ComfyUI로 '꼬마 카트 랠리' 그림을 생성한다 (사용자 PC에서 실행).

ComfyUI가 켜져 있는 PC에서, ComfyUI에 들어 있는 파이썬으로 실행하면 된다.

    cd C:\\AI\\ComfyUI_windows_portable
    .\\python_embeded\\python.exe C:\\경로\\racing-sim\\tools\\comfy_generate.py

결과: racing-sim/kart2d/assets/ 에 PNG와 manifest.json 이 생긴다.
게임은 이 폴더에 그림이 있으면 그 그림을 쓰고, 없으면 원래 코드 그림을 쓴다.

옵션
    --server http://127.0.0.1:8188   ComfyUI 주소
    --ckpt  이름.safetensors         사용할 체크포인트 (생략하면 목록에서 자동 선택)
    --only  racer|decor|all          일부만 다시 만들기
    --seed  1234                     시드 고정 (같은 그림 다시 만들기)
    --steps 25                       샘플링 스텝 수
"""
import argparse
import io
import json
import pathlib
import random
import sys
import time
import urllib.parse
import urllib.request
import uuid

try:
    from PIL import Image
except ImportError:  # ComfyUI 내장 파이썬에는 Pillow가 들어 있다
    sys.exit("Pillow가 필요합니다. ComfyUI 폴더의 python_embeded\\python.exe 로 실행해 주세요.")

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "kart2d" / "assets"

STYLE = ("cute kawaii chibi game art, flat vector illustration, clean thick dark purple outline, "
         "soft pastel colors, simple cel shading, centered, isolated on plain pure white background")
NEGATIVE = ("text, letters, watermark, signature, logo, frame, border, realistic, photo, 3d render, "
            "blurry, noisy, dark background, gradient background, shadow on background, cropped, "
            "multiple characters, extra limbs, deformed, ugly")

# 게임 레이서와 같은 순서 (RACERS 배열)
RACERS = [
    ("volt", "fox", "orange fox with white muzzle", "red"),
    ("mimi", "bunny", "white bunny with long pink ears", "pink"),
    ("kai", "bear", "brown bear cub", "sky blue"),
    ("lulu", "cat", "cream colored cat with pink inner ears", "yellow"),
    ("deokgu", "puppy", "beige puppy with floppy brown ears", "brown"),
    ("piko", "frog", "green frog with big round eyes", "green"),
    ("jelly", "alien", "lavender little alien with one antenna", "purple"),
    ("toto", "hamster", "orange and white hamster with chubby cheeks", "orange"),
]
DECOR = {
    "tree": "a round fluffy green tree with short brown trunk, single tree",
    "bush": "a small round green bush with tiny red berries",
    "mushroom": "a cute red mushroom with white dots",
    "cactus": "a cute green cactus with two arms and a pink flower on top",
    "rock": "a smooth rounded orange desert rock",
    "pine": "a green pine tree with snow on the branches",
    "snowman": "a cute snowman with red scarf and carrot nose",
}


def http_json(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"} if body else {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def pick_checkpoint(server, wanted):
    info = http_json(f"{server}/object_info/CheckpointLoaderSimple")
    names = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    if not names:
        sys.exit("ComfyUI\\models\\checkpoints 폴더에 체크포인트가 없습니다. SD1.5 또는 SDXL 모델을 넣어 주세요.")
    if wanted:
        if wanted not in names:
            sys.exit(f"'{wanted}' 체크포인트가 없습니다. 사용 가능: {', '.join(names)}")
        return wanted, names
    # SDXL 계열을 우선 (그림 품질), 없으면 첫 번째
    xl = [n for n in names if "xl" in n.lower()]
    return (xl or names)[0], names


def workflow(ckpt, pos, neg, w, h, seed, steps):
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
            "seed": seed, "steps": steps, "cfg": 6.5, "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "kart_rally"}},
    }


def generate(server, wf):
    client_id = str(uuid.uuid4())
    pid = http_json(f"{server}/prompt", {"prompt": wf, "client_id": client_id})["prompt_id"]
    for _ in range(600):
        time.sleep(1)
        hist = http_json(f"{server}/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                sys.exit(f"ComfyUI 오류: {json.dumps(status.get('messages', []), ensure_ascii=False)[:500]}")
            for out in entry.get("outputs", {}).values():
                for img in out.get("images", []):
                    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")})
                    with urllib.request.urlopen(f"{server}/view?{q}", timeout=60) as r:
                        return Image.open(io.BytesIO(r.read())).convert("RGBA")
    sys.exit("10분 안에 생성이 끝나지 않았습니다.")


def remove_white_bg(img, tol=28):
    """가장자리에서 이어진 흰 배경만 투명하게 (캐릭터 안의 흰색은 유지)."""
    w, h = img.size
    px = img.load()
    seen = bytearray(w * h)
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    def bgish(p):
        r, g, b, _ = p
        return r > 255 - tol and g > 255 - tol and b > 255 - tol and max(r, g, b) - min(r, g, b) < tol
    while stack:
        x, y = stack.pop()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        if not bgish(px[x, y]):
            continue
        px[x, y] = (255, 255, 255, 0)
        if x > 0: stack.append((x - 1, y))
        if x < w - 1: stack.append((x + 1, y))
        if y > 0: stack.append((x, y - 1))
        if y < h - 1: stack.append((x, y + 1))
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def fit(img, size):
    img = img.copy()
    img.thumbnail((size, size), Image.LANCZOS)
    return img


def main():
    ap = argparse.ArgumentParser(description="ComfyUI로 꼬마 카트 랠리 그림 생성")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--ckpt")
    ap.add_argument("--only", choices=["racer", "decor", "all"], default="all")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--steps", type=int, default=25)
    args = ap.parse_args()
    server = args.server.rstrip("/")

    try:
        http_json(f"{server}/system_stats")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"ComfyUI({server})에 연결할 수 없습니다. ComfyUI를 먼저 실행해 주세요. ({e})")

    ckpt, names = pick_checkpoint(server, args.ckpt)
    xl = "xl" in ckpt.lower()
    size = 1024 if xl else 512
    print(f"체크포인트: {ckpt}  ({'SDXL' if xl else 'SD1.5'} 기준 {size}px)")
    print(f"(사용 가능: {', '.join(names)})")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"racers": {}, "decor": {}}
    seed0 = args.seed if args.seed is not None else random.randint(0, 2**31)

    jobs = []
    if args.only in ("racer", "all"):
        for i, (key, animal, look, color) in enumerate(RACERS):
            pos = (f"portrait of a {look} wearing a tiny {color} racing helmet with goggles, smiling, "
                   f"head and shoulders, facing the viewer, {STYLE}")
            jobs.append(("racers", str(i), f"racer_{key}.png", pos, 256))
    if args.only in ("decor", "all"):
        for key, desc in DECOR.items():
            jobs.append(("decor", key, f"decor_{key}.png", f"{desc}, side view, full object visible, {STYLE}", 256))

    for n, (group, key, fname, pos, px) in enumerate(jobs, 1):
        t0 = time.time()
        print(f"[{n}/{len(jobs)}] {fname} 생성 중…", end="", flush=True)
        img = generate(server, workflow(ckpt, pos, NEGATIVE, size, size, seed0 + n, args.steps))
        img = fit(remove_white_bg(img), px)
        img.save(OUT / fname)
        manifest[group][key] = fname
        print(f" 완료 ({time.time() - t0:.0f}초)")

    manifest["model"] = ckpt
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료! {OUT} 에 저장했습니다.")
    print("GitHub에 올리면 1~2분 뒤 게임에 반영됩니다:")
    print("    git add kart2d/assets && git commit -m \"ComfyUI 그림 추가\" && git push")


if __name__ == "__main__":
    main()
