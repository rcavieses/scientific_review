#!/usr/bin/env python3
"""Construye la cita completa de cada paper del índice RAG.

El `metadata_store.json` sólo guarda el nombre de archivo (`paper_id`) y casi
nunca título, autores ni DOI. Este script recupera el DOI del texto de la
portada, consulta CrossRef y deja `paper_references.json`, que el buscador usa
para citar en formato completo. Si no hay DOI, busca por el texto de portada y
sólo acepta el resultado si su título aparece en esa portada.

    python3 scripts/phase_6_query/build_paper_references.py
    python3 scripts/phase_6_query/build_paper_references.py --semilla refs.json
"""
import argparse, collections, html, json, re, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX = ROOT / "outputs" / "rag_index_goc_full"
OUT = INDEX / "paper_references.json"
HDR = {"User-Agent": "scientific-review (mailto:rcavieses@gmail.com)"}
DOI = re.compile(r"(?:doi\.org/|doi:\s*|DOI\s*:?\s*)(10\.\d{4,9}/[^\s\"'<>,;)\]]+)", re.I)
DOI_ANY = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>,;)\]]+)")


def limpiar(s):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", "", html.unescape(s))).strip()


def formato(m):
    au = []
    for a in m.get("author", []):
        fam = a.get("family") or a.get("name", ""); g = a.get("given", "")
        ini = " ".join(w[0] + "." for w in re.split(r"[\s-]+", g) if w)
        au.append(f"{fam}, {ini}".strip(", "))
    a = ", ".join(au[:-1]) + ", & " + au[-1] if len(au) > 1 else (au[0] if au else "")
    y = (m.get("issued", {}).get("date-parts") or [[None]])[0][0]
    t = (m.get("title") or [""])[0].rstrip("."); j = (m.get("container-title") or [""])[0]
    if not t:
        return None
    s = f"{a} ({y}). {t}. {j}"
    if m.get("volume"): s += f", {m['volume']}"
    if m.get("issue"): s += f"({m['issue']})"
    if m.get("page"): s += f", {m['page']}"
    return limpiar(s + f". https://doi.org/{m['DOI']}")


def solapa(titulo, texto):
    pal = {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ]{5,}", limpiar(titulo))}
    base = re.sub(r"\s+", "", texto.lower())
    return sum(re.sub(r"\s+", "", w) in base for w in pal) / max(1, len(pal))


def get(url, **kw):
    for _ in range(3):
        try:
            r = requests.get(url, headers=HDR, timeout=30, **kw)
            if r.ok and r.text.startswith("{"):
                return r.json()["message"]
            if r.status_code == 404:
                return None
        except requests.RequestException:
            pass
        time.sleep(2)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semilla", help="JSON {paper_id: cita} ya verificado a mano")
    args = ap.parse_args()
    store = json.loads((INDEX / "metadata_store.json").read_text(encoding="utf-8"))
    papers = collections.defaultdict(list)
    for r in store.values():
        papers[r["paper_id"]].append(r)
    refs = json.loads(OUT.read_text()) if OUT.exists() else {}
    if args.semilla:
        for k, v in json.loads(Path(args.semilla).read_text()).items():
            refs[k] = {"cita": v, "origen": "verificada"}
    for i, (pid, rs) in enumerate(sorted(papers.items()), 1):
        if pid in refs:
            continue
        rs.sort(key=lambda r: int(r["chunk_index"]))
        front = " ".join(r["text"] for r in rs[:2])
        m = DOI.search(front) or DOI_ANY.search(front)
        cita, origen = None, None
        if m:
            doi = m.group(1).rstrip(".,;")
            msg = get("https://api.crossref.org/works/" + requests.utils.quote(doi, safe="/()<>:;[]"))
            if msg and solapa((msg.get("title") or [""])[0], front) >= 0.7:
                cita, origen = formato(msg), "crossref_doi"
        if not cita:
            r = get("https://api.crossref.org/works", params={"query.bibliographic": rs[0]["text"][:300], "rows": 1})
            it = (r or {}).get("items", [None])[0] if r else None
            if it and solapa((it.get("title") or [""])[0], front) >= 0.8 and it.get("score", 0) > 60:
                cita, origen = formato(it), "crossref_titulo"
        refs[pid] = {"cita": cita, "origen": origen or "no_resuelta",
                     "portada": None if cita else limpiar(rs[0]["text"][:200])}
        time.sleep(0.15)
        if i % 25 == 0:
            OUT.write_text(json.dumps(refs, ensure_ascii=False, indent=1))
            print(i, len(papers), flush=True)
    OUT.write_text(json.dumps(refs, ensure_ascii=False, indent=1))
    c = collections.Counter(v["origen"] for v in refs.values())
    print(dict(c))


if __name__ == "__main__":
    main()
