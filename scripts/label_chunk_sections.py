#!/usr/bin/env python3
"""Etiqueta cada chunk del índice según su posición y su función en el documento.

Motivación: las listas de referencias bibliográficas entran al top_k y gastan
contexto sin aportar datos (medido: 32 % de las consultas arrastran al menos una).
No hace falta reindexar — `chunk_index`, `total_chunks` y el propio texto bastan.

Etiquetas:
  cover              chunk 0: portada, con título, revista y a menudo el DOI
  references         lista de referencias (alta confianza)
  references_likely  probable bibliografía al final del documento
  table              alta densidad numérica: tabla de datos, NUNCA se descarta
  body               el resto

La distinción `table` es deliberada: una tabla de datos comparte rasgos con una
lista de referencias (números, años, apellidos) y es justo donde viven los
parámetros que buscamos —la biomasa de Micropogonias megalops salió de una—.
Ante la duda, gana `table`.

Salida: outputs/rag_index_goc_full/chunk_sections.json

Uso:
    python3 scripts/label_chunk_sections.py
    python3 scripts/label_chunk_sections.py --sample 8   # inspección manual
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = PROJECT_ROOT / "outputs" / "rag_index_goc_full"
STORE = INDEX_DIR / "metadata_store.json"
OUTPUT = INDEX_DIR / "chunk_sections.json"

# "Smith, J.A.," — apellido seguido de iniciales: la firma de una entrada bibliográfica
INITIALS = re.compile(r"[A-ZÁÉÍÓÚÑ][a-záéíóúñ\-]{2,},\s*[A-Z]\.(?:\s*[A-Z]\.)*")
YEAR = re.compile(r"(?:\(|\s)(?:19|20)\d{2}[a-z]?(?:\)|\.|,)")
JOURNAL = re.compile(r"\b(?:Journal|J\.\s|Rev\.|Bull\.|Mar\.|Ecol\.|Fish\.|Proc\.|Sci\.|Vol\.|pp\.|doi:|https?://doi)", re.I)
HEADING = re.compile(r"(REFERENCES|LITERATURE CITED|BIBLIOGRAF|REFER[ÊE]NCIAS|LITERATURA CITADA)", re.I)
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")

REF_SCORE_MIN = 3.5
REF_SCORE_MAYBE = 2.0
TABLE_DENSITY = 0.35


def features(text: str) -> dict:
    per500 = max(len(text) / 500, 1)
    words = max(len(text.split()), 1)
    return {
        "initials": len(INITIALS.findall(text)) / per500,
        "years": len(YEAR.findall(text)) / per500,
        "journal": len(JOURNAL.findall(text)) / per500,
        "heading": bool(HEADING.search(text)),
        "num_density": len(NUMBER.findall(text)) / words,
    }


def classify(text: str, rel_pos: float, chunk_index: int) -> tuple[str, float]:
    f = features(text)
    score = f["initials"] * 1.5 + f["years"] * 0.8 + f["journal"] * 0.4 + (3 if f["heading"] else 0)

    if chunk_index == 0:
        return "cover", round(score, 2)

    # Una tabla de datos gana siempre: preferimos leer una tabla de más que
    # perder la única celda que contiene el parámetro.
    if f["num_density"] > TABLE_DENSITY and f["initials"] < 1.5:
        return "table", round(score, 2)

    if (score >= REF_SCORE_MIN and rel_pos >= 0.55) or (f["heading"] and rel_pos >= 0.4):
        return "references", round(score, 2)
    if score >= REF_SCORE_MAYBE and rel_pos >= 0.80:
        return "references_likely", round(score, 2)
    return "body", round(score, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=int, default=0, help="Muestra N chunks por etiqueta para revisar a ojo")
    args = parser.parse_args()

    store = json.loads(STORE.read_text(encoding="utf-8"))
    labels: dict[str, dict] = {}
    by_label: dict[str, list] = {}

    for record in store.values():
        total = max(record.get("total_chunks") or 1, 1)
        index = record.get("chunk_index", 0)
        rel_pos = (index + 1) / total
        label, score = classify(record.get("text", ""), rel_pos, index)
        labels[record["chunk_id"]] = {
            "section": label,
            "ref_score": score,
            "rel_pos": round(rel_pos, 3),
            "page": record.get("page_number"),
        }
        by_label.setdefault(label, []).append(record)

    OUTPUT.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")

    counts = Counter(v["section"] for v in labels.values())
    total = len(labels)
    print(f"✓ {OUTPUT.relative_to(PROJECT_ROOT)}  ({total} chunks)")
    for label, n in counts.most_common():
        print(f"   {label:18s} {n:6d}  ({n / total * 100:5.1f}%)")
    demoted = counts["references"] + counts["references_likely"]
    print(f"\n   se relegarán en la recuperación: {demoted} ({demoted / total * 100:.1f}%)")

    if args.sample:
        random.seed(5)
        for label, records in by_label.items():
            print(f"\n=== {label} ===")
            for record in random.sample(records, min(args.sample, len(records))):
                info = labels[record["chunk_id"]]
                print(f"  [pos {info['rel_pos']:.2f} score {info['ref_score']:5.1f}] "
                      f"{record['text'][:100]!r}")


if __name__ == "__main__":
    main()
