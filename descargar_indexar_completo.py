"""
Script para descargar e indexar TODOS los artículos encontrados.
"""
import subprocess
import time
from pathlib import Path

print("\n" + "="*80)
print("DESCARGANDO E INDEXANDO TODOS LOS ARTÍCULOS PARA 12 ESPECIES")
print("="*80 + "\n")

inicio = time.time()

# Ejecutar descarga e indexación
print("Fase 1: Descargando PDFs en acceso abierto (puede tomar 20-30 minutos)...")
print("-" * 80)

cmd = [
    "python", "pipeline_especies.py",
    "--download",
    "--index",
    "--max-results", "30",
    "--year-start", "2015"
]

try:
    resultado = subprocess.run(cmd, capture_output=False, text=True, timeout=7200)
    if resultado.returncode == 0:
        print("\n✅ Descarga e indexación completada exitosamente")
    else:
        print(f"\n⚠️ Algún warning durante la ejecución")
except subprocess.TimeoutExpired:
    print("\n❌ Timeout (> 2 horas)")
except Exception as e:
    print(f"\n❌ Error: {e}")

tiempo_total = time.time() - inicio

print("\n" + "="*80)
print(f"Tiempo total: {tiempo_total/60:.1f} minutos")
print("="*80)

# Verificar resultados
print("\n✓ Verificando resultados...")
pdfs = list(Path("outputs/pdfs").glob("*.pdf"))
print(f"  PDFs descargados: {len(pdfs)}")

rag_index = Path("outputs/rag_index/index.faiss")
if rag_index.exists():
    size_mb = rag_index.stat().st_size / (1024*1024)
    print(f"  Índice FAISS: {size_mb:.1f} MB")
    print("\n✅ RAG Index actualizado y listo para consultas")

