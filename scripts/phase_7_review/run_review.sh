#!/bin/bash
# Lanza el tablero de revisión manual de parámetros.
#
#   ./scripts/phase_7_review/run_review.sh              # puerto 8600
#   ./scripts/phase_7_review/run_review.sh 8700         # otro puerto
#   REBUILD=1 ./scripts/phase_7_review/run_review.sh    # regenera la cola antes
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PORT="${1:-8600}"
PY="${ROOT}/venv/bin/python"
[ -x "$PY" ] || PY="python3"

cd "$ROOT"

if [ "${REBUILD:-0}" = "1" ] || [ ! -f outputs/review/review_queue.json ]; then
  echo "→ Construyendo la cola de revisión…"
  "$PY" scripts/phase_7_review/build_review_queue.py
fi

echo "→ Tablero en http://127.0.0.1:${PORT}"
exec "$PY" scripts/phase_7_review/review_server.py --port "$PORT"
