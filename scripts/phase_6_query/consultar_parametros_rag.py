"""
Script para consultar parámetros poblacionales de cada especie usando RAG.

Este script:
1. Descarga PDFs de los artículos encontrados
2. Indexa los PDFs en FAISS
3. Realiza consultas RAG sobre parámetros poblacionales (K, r, M, etc.)
4. Recopila métricas de rendimiento
5. Genera un reporte con los resultados

Uso:
    python consultar_parametros_rag.py
    python consultar_parametros_rag.py --skip-download
    python consultar_parametros_rag.py --skip-index
"""
import argparse
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
import sys
import io

# Forzar UTF-8 en salida
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# Definición de especies y parámetros a consultar
ESPECIES_PARAMETROS = [
    {
        "nombre": "Sardina Pacific",
        "nombre_cientifico": "Sardinops sagax",
        "preguntas": [
            "What are the population parameters (K, r, M) for Sardinops sagax in the Gulf of California?",
            "Describe the stock assessment and fishing mortality rates for Pacific sardine in the Gulf of California",
            "What are the recruitment patterns and reproductive parameters for Sardinops sagax?",
        ]
    },
    {
        "nombre": "Calamar Gigante",
        "nombre_cientifico": "Dosidicus gigas",
        "preguntas": [
            "What population parameters are available for Dosidicus gigas (jumbo squid) in the Gulf of California?",
            "Describe growth rates, maturation age, and lifespan of Dosidicus gigas",
            "What are the biomass estimates and fishing mortality for jumbo squid?",
        ]
    },
    {
        "nombre": "Atún Aleta Amarilla",
        "nombre_cientifico": "Thunnus albacares",
        "preguntas": [
            "What are the population parameters for Thunnus albacares (yellowfin tuna) in the Eastern Pacific?",
            "Describe the growth, natural mortality, and recruitment of yellowfin tuna in the Gulf of California",
            "What are the current stock status and fishing mortality estimates for Thunnus albacares?",
        ]
    },
    {
        "nombre": "Pargo Colorado",
        "nombre_cientifico": "Lutjanus peru",
        "preguntas": [
            "What population parameters are reported for Lutjanus peru (red snapper) in the Gulf of California?",
            "Describe the growth parameters (L-infinity, K) and natural mortality for red snapper",
            "What are the recruitment and settlement patterns of Lutjanus peru?",
        ]
    },
]


def descargar_e_indexar_pdfs(verbose=True):
    """Descarga e indexa PDFs de todos los artículos encontrados."""
    print("\n" + "="*80)
    print("PASO 1: DESCARGAR E INDEXAR PDFs")
    print("="*80)

    inicio = time.time()

    # Ejecutar descarga e indexación
    cmd = [
        "python", "pipeline_especies.py",
        "--download", "--index"
    ]

    try:
        if verbose:
            print("\nEjecutando: python pipeline_especies.py --download --index\n")
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

        if resultado.returncode == 0:
            print("✓ Descarga e indexación completada exitosamente")
        else:
            print(f"✗ Error en descarga/indexación: {resultado.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Timeout en descarga/indexación (> 1 hora)")
        return False
    except Exception as e:
        print(f"✗ Error durante descarga/indexación: {e}")
        return False

    tiempo_indexacion = time.time() - inicio
    print(f"Tiempo de indexación: {tiempo_indexacion:.2f} segundos")
    return True


def consultar_rag_parametros(top_k=5, verbose=True):
    """Consulta RAG por parámetros poblacionales de cada especie."""
    print("\n" + "="*80)
    print("PASO 2: CONSULTAS RAG - PARÁMETROS POBLACIONALES")
    print("="*80)

    from pipeline.rag import VectorDBManager
    from pipeline.rag.query_engine import RAGQueryEngine

    index_dir = Path("outputs/rag_index")

    # Verificar que el índice existe
    config_path = index_dir / "index_config.json"
    if not config_path.exists():
        print(f"✗ No se encontró índice en '{index_dir}'")
        print("  Ejecuta: python pipeline_especies.py --download --index")
        return None

    # Cargar índice
    with open(config_path) as f:
        index_config = json.load(f)
    embedding_dim = index_config["embedding_dimension"]

    db = VectorDBManager(index_dir=index_dir, embedding_dim=embedding_dim, verbose=False)
    if not db.load():
        print("✗ No se pudo cargar el índice")
        return None

    stats = db.get_stats()
    print(f"\nÍndice cargado: {stats.total_chunks} chunks de {stats.total_papers} papers")
    print(f"Modelo: {stats.embedding_model} | top_k={top_k}\n")

    # Inicializar query engine
    engine = RAGQueryEngine(
        vector_db=db,
        model="claude-haiku-4-5-20251001",
        top_k=top_k,
        max_tokens=1024,
        min_score=0.2,
        verbose=False
    )

    resultados = {
        "timestamp": datetime.now().isoformat(),
        "indice_stats": {
            "total_chunks": stats.total_chunks,
            "total_papers": stats.total_papers,
            "embedding_model": stats.embedding_model,
            "embedding_dimension": stats.embedding_dimension,
            "index_size_mb": float(stats.index_size_mb)
        },
        "parametros_poblacionales": {},
        "metricas": {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "avg_response_time": 0,
            "avg_chunks_used": 0
        }
    }

    response_times = []
    chunks_used_list = []

    for especie_idx, especie in enumerate(ESPECIES_PARAMETROS, 1):
        print(f"\n[{especie_idx}] {especie['nombre']} ({especie['nombre_cientifico']})")
        print("-" * 70)

        especie_results = {
            "nombre": especie['nombre'],
            "nombre_cientifico": especie['nombre_cientifico'],
            "consultas": []
        }

        for pregunta_idx, pregunta in enumerate(especie['preguntas'], 1):
            print(f"\n  Pregunta {pregunta_idx}/{len(especie['preguntas'])}:")
            print(f"  {pregunta[:70]}...")

            inicio_query = time.time()

            try:
                resultado = engine.query(pregunta)
                tiempo_query = time.time() - inicio_query

                response_times.append(tiempo_query)
                chunks_used = len(resultado.sources) if resultado.sources else 0
                chunks_used_list.append(chunks_used)

                respuesta_corta = resultado.answer[:200] + "..." if len(resultado.answer) > 200 else resultado.answer
                print(f"  ✓ Respuesta obtenida ({tiempo_query:.2f}s, {chunks_used} chunks)")

                especie_results['consultas'].append({
                    "pregunta": pregunta,
                    "respuesta": resultado.answer,
                    "chunks_utilizados": chunks_used,
                    "tiempo_respuesta": tiempo_query,
                    "fuentes": [str(s) for s in resultado.sources[:3]] if resultado.sources else []
                })

                resultados["metricas"]["successful_queries"] += 1

            except Exception as e:
                print(f"  ✗ Error en consulta: {str(e)[:100]}")
                especie_results['consultas'].append({
                    "pregunta": pregunta,
                    "error": str(e),
                    "respuesta": None
                })
                resultados["metricas"]["failed_queries"] += 1

            resultados["metricas"]["total_queries"] += 1

        resultados["parametros_poblacionales"][especie['nombre_cientifico']] = especie_results

    # Calcular métricas promedio
    if response_times:
        resultados["metricas"]["avg_response_time"] = sum(response_times) / len(response_times)
    if chunks_used_list:
        resultados["metricas"]["avg_chunks_used"] = sum(chunks_used_list) / len(chunks_used_list)

    return resultados


def generar_reporte_markdown(resultados):
    """Genera un reporte markdown con todos los resultados y métricas."""
    if not resultados:
        print("✗ No hay resultados para generar reporte")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reporte_path = Path(f"outputs/REPORTE_RAG_PARAMETROS_{timestamp}.md")

    markdown = f"""# Reporte: Consultas RAG para Parámetros Poblacionales
## Golfo de California - 12 Especies Importantes

**Fecha de Ejecución**: {resultados['timestamp']}
**Generado**: {datetime.now().strftime('%d de %B, %Y a las %H:%M:%S')}

---

## 📊 Resumen Ejecutivo

### Estadísticas del Índice RAG
- **Total de Chunks**: {resultados['indice_stats']['total_chunks']:,}
- **Total de Papers Indexados**: {resultados['indice_stats']['total_papers']}
- **Modelo de Embeddings**: {resultados['indice_stats']['embedding_model']}
- **Dimensión de Embeddings**: {resultados['indice_stats']['embedding_dimension']}
- **Tamaño del Índice**: {resultados['indice_stats']['index_size_mb']:.2f} MB

### Métricas de Rendimiento
- **Consultas Totales**: {resultados['metricas']['total_queries']}
- **Consultas Exitosas**: {resultados['metricas']['successful_queries']}
- **Consultas Fallidas**: {resultados['metricas']['failed_queries']}
- **Tasa de Éxito**: {(resultados['metricas']['successful_queries'] / max(resultados['metricas']['total_queries'], 1) * 100):.1f}%
- **Tiempo Promedio de Respuesta**: {resultados['metricas']['avg_response_time']:.2f} segundos
- **Chunks Promedio Utilizados**: {resultados['metricas']['avg_chunks_used']:.1f}

---

## 🔬 Parámetros Poblacionales Extraídos

"""

    # Agregar resultados por especie
    for especie_cient, especie_data in resultados['parametros_poblacionales'].items():
        markdown += f"\n### {especie_data['nombre']} ({especie_cient})\n\n"

        for idx, consulta in enumerate(especie_data['consultas'], 1):
            markdown += f"#### Consulta {idx}\n\n"
            markdown += f"**Pregunta**: {consulta['pregunta']}\n\n"

            if 'error' in consulta:
                markdown += f"**Estado**: ❌ Error\n"
                markdown += f"**Detalles**: {consulta['error']}\n\n"
            else:
                markdown += f"**Respuesta**:\n\n"
                markdown += f"{consulta['respuesta']}\n\n"

                if consulta['chunks_utilizados'] > 0:
                    markdown += f"**Fuentes**: {consulta['chunks_utilizados']} chunks recuperados\n"
                    if consulta['fuentes']:
                        markdown += "- " + "\n- ".join(consulta['fuentes'][:3]) + "\n\n"
                    else:
                        markdown += "\n"

                markdown += f"**Tiempo de Respuesta**: {consulta['tiempo_respuesta']:.2f}s\n\n"

        markdown += "---\n"

    # Agregar sección de análisis
    markdown += """
## 📈 Análisis de Rendimiento

### Tiempo de Respuesta por Consulta
"""

    tiempos = []
    for especie_data in resultados['parametros_poblacionales'].values():
        for consulta in especie_data['consultas']:
            if 'tiempo_respuesta' in consulta:
                tiempos.append(consulta['tiempo_respuesta'])

    if tiempos:
        markdown += f"- **Mínimo**: {min(tiempos):.2f}s\n"
        markdown += f"- **Máximo**: {max(tiempos):.2f}s\n"
        markdown += f"- **Promedio**: {sum(tiempos) / len(tiempos):.2f}s\n"
        markdown += f"- **Mediana**: {sorted(tiempos)[len(tiempos)//2]:.2f}s\n\n"

    markdown += """
### Cobertura de Información
"""

    especies_con_datos = sum(
        1 for especie_data in resultados['parametros_poblacionales'].values()
        if any('respuesta' in q and q['respuesta'] for q in especie_data['consultas'])
    )

    markdown += f"- **Especies con datos extraídos**: {especies_con_datos}/{len(resultados['parametros_poblacionales'])}\n"
    markdown += f"- **Tasa de cobertura**: {(especies_con_datos / len(resultados['parametros_poblacionales']) * 100):.0f}%\n\n"

    markdown += """
---

## 🎯 Conclusiones

"""

    # Conclusiones basadas en los resultados
    if resultados['metricas']['total_queries'] > 0:
        tasa_exito = resultados['metricas']['successful_queries'] / resultados['metricas']['total_queries']

        if tasa_exito >= 0.8:
            markdown += "✅ **Excelente cobertura**: El RAG recuperó información relevante para la mayoría de las especies.\n\n"
        elif tasa_exito >= 0.6:
            markdown += "⚠️ **Cobertura moderada**: El RAG recuperó información para muchas especies, pero hay margen de mejora.\n\n"
        else:
            markdown += "⚠️ **Cobertura limitada**: Se recomienda descargar más artículos o indexar más papers.\n\n"

        if resultados['metricas']['avg_response_time'] < 5:
            markdown += "✅ **Rendimiento excelente**: Tiempos de respuesta rápidos.\n\n"
        elif resultados['metricas']['avg_response_time'] < 10:
            markdown += "⚠️ **Rendimiento aceptable**: Los tiempos de respuesta son razonables.\n\n"
        else:
            markdown += "⚠️ **Rendimiento lento**: Considere optimizar el índice o usar menos chunks.\n\n"

    markdown += """
## 📝 Próximos Pasos Recomendados

1. **Expansión del Índice**: Descargar más papers (incrementar --max-results)
2. **Optimización de Búsqueda**: Ajustar top_k y min_score para mejores resultados
3. **Validación de Datos**: Cruzar los parámetros extraídos con bases de datos (FishBase, CITES)
4. **GraphRAG**: Construir un grafo de conocimiento para consultas más sofisticadas
5. **Análisis Comparativo**: Comparar parámetros entre especies del Golfo

---

## 📚 Referencias

- Golfo de California Initiative: https://www.gulfofcalifornia.org/
- FishBase: https://www.fishbase.se/
- FAO FishStat: http://www.fao.org/fishstat/
- ICES Stock Assessment: https://www.ices.dk/

---

*Documento generado automáticamente por el pipeline de Scientific Review*
"""

    with open(reporte_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    print(f"\n✓ Reporte generado: {reporte_path}")
    return reporte_path


def main():
    parser = argparse.ArgumentParser(
        description="Consultar parámetros poblacionales usando RAG"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Saltar descarga de PDFs (usar índice existente)"
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Saltar indexación de PDFs"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Número de chunks a recuperar (default: 5)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar logs detallados"
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("PIPELINE DE CONSULTAS RAG - PARÁMETROS POBLACIONALES")
    print("="*80)
    print(f"\nFecha de inicio: {datetime.now().strftime('%d de %B, %Y a las %H:%M:%S')}")

    inicio_total = time.time()

    # Paso 1: Descargar e Indexar
    if not args.skip_download and not args.skip_index:
        if not descargar_e_indexar_pdfs(verbose=args.verbose):
            print("\n✗ Fallo en descarga/indexación")
            return

    # Paso 2: Consultas RAG
    print("\n")
    resultados = consultar_rag_parametros(top_k=args.top_k, verbose=args.verbose)

    if not resultados:
        print("✗ No se pudieron obtener resultados")
        return

    # Paso 3: Generar Reporte
    print("\n" + "="*80)
    print("PASO 3: GENERANDO REPORTE MARKDOWN")
    print("="*80)
    generar_reporte_markdown(resultados)

    # Guardar resultados JSON
    json_path = Path(f"outputs/resultados_rag_parametros_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"✓ Resultados JSON guardados: {json_path}")

    tiempo_total = time.time() - inicio_total

    print("\n" + "="*80)
    print("✅ PIPELINE COMPLETADO EXITOSAMENTE")
    print("="*80)
    print(f"\nTiempo total de ejecución: {tiempo_total:.2f} segundos ({tiempo_total/60:.1f} minutos)")
    print(f"Fecha de finalización: {datetime.now().strftime('%d de %B, %Y a las %H:%M:%S')}")


if __name__ == "__main__":
    main()
