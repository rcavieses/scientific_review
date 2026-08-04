#!/usr/bin/env python3
"""
Script para descargar y cachear localmente el modelo de embeddings.

Uso:
    python3 setup_embeddings.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

def setup_embeddings():
    """Descarga el modelo de embeddings localmente."""
    cache_dir = PROJECT_ROOT / "models" / "embeddings"
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"📦 Descargando modelo de embeddings a: {cache_dir}")
    print("   (Primera ejecución: ~30-50 segundos)\n")

    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            'all-MiniLM-L6-v2',
            cache_folder=str(cache_dir)
        )

        dim = model.get_embedding_dimension()
        size_mb = (cache_dir / "modules.json").stat().st_size / 1024 / 1024 if (cache_dir / "modules.json").exists() else 0

        print(f"✅ Modelo descargado correctamente")
        print(f"   • Modelo: all-MiniLM-L6-v2")
        print(f"   • Dimensión: {dim}D")
        print(f"   • Ubicación: {cache_dir}\n")

        # Mostrar tamaño total
        import os
        total_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
        size_mb = total_size / 1024 / 1024
        print(f"   • Tamaño total: {size_mb:.0f} MB\n")

        print("✅ Setup completado. Ahora puedes hacer consultas sin descargas.")
        print("\nEjecuta:")
        print("  ./iniciar_rag.sh          # Para la web UI")
        print("  python3 scripts/phase_6_query/buscar_rag_con_fishbase.py --interactive  # CLI")

        return True

    except ImportError:
        print("❌ Error: sentence-transformers no está instalado")
        print("   Ejecuta: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Error descargando modelo: {str(e)}")
        return False

if __name__ == "__main__":
    success = setup_embeddings()
    sys.exit(0 if success else 1)
