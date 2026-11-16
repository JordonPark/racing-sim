#!/usr/bin/env python3
"""웹 배포용 dist/ 폴더를 만든다.

kart/index.html, web/index.html은 문서 머리말(<!doctype>, charset) 없이 작성되어 있어
(claude.ai Artifact가 게시할 때 자동으로 붙여 줌) 일반 웹 호스팅에서는 그대로 쓰면
한글 인코딩·표준 모드 문제가 생길 수 있다. 여기서 머리말을 붙여 dist/에 복사한다.

    python3 build.py      # → dist/index.html, dist/kart/index.html, dist/web/index.html
"""
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parent
DIST = ROOT / "dist"

HEAD = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<style>body{margin:0}[hidden]{display:none!important}img{max-width:100%}</style>
"""

PAGES = ["kart/index.html", "web/index.html"]


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copy(ROOT / "index.html", DIST / "index.html")
    for rel in PAGES:
        src = (ROOT / rel).read_text(encoding="utf-8")
        if not src.lstrip().lower().startswith("<!doctype"):
            src = HEAD + src
        out = DIST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(src, encoding="utf-8")
    for p in sorted(DIST.rglob("*.html")):
        print(p.relative_to(ROOT), p.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
