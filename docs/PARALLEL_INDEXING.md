# Estrategia Mixta de Indexación Paralela

## Resumen

Combina 4 técnicas para procesar 42K PDFs en **~2-3 semanas** en lugar de 3+ meses:

| Técnica | Beneficio | Factor |
|---------|-----------|--------|
| **Provider Local** | 2-3x más rápido que Ollama | 2.5x |
| **Chunk Size 1024** | 30% menos embeddings | 1.3x |
| **Procesos Paralelos** | 4 procesos simultáneos | 4x |
| **Índices Temporales** | Evita contención de locks | - |
| | **Total estimado** | **~13 días** |

## Ejecución

### Paso 1: Iniciar indexación paralela

```bash
# Terminal 1: Ejecutar indexador paralelo
nohup python3 indexar_paralelo.py > indexar_paralelo.log 2>&1 &

# Monitorear progreso en tiempo real
tail -f indexar_paralelo.log
```

### Paso 2: Monitorear progreso

```bash
# Ver batches activos
ps aux | grep indexar.py | grep -v grep | wc -l

# Ver resumen cada hora
watch -n 3600 'tail -30 indexar_paralelo.log'
```

### Paso 3: Cuando todos los batches terminen

```bash
# Fusionar índices temporales en uno final
python3 merge_indices.py

# Verificar resultado
python3 indexar.py --stats
```

## Configuración

Editar `indexar_paralelo.py` para ajustar:

```python
MAX_WORKERS = 4           # Aumentar si tienes más cores
BATCH_SIZE = 50           # Más grande = batches más lentos pero menos overhead
CHUNK_SIZE = 1024         # Aumentar = menos chunks = más rápido (menos preciso)
PROVIDER = "local"        # "ollama" si prefieres
MODEL = "all-mpnet-base-v2"  # O "all-MiniLM-L6-v2" para más velocidad
```

## Ventajas de esta estrategia

✅ **Paralelización real**: 4 procesos Python independientes  
✅ **Sin contención de locks**: Cada batch usa índice separado  
✅ **Escalable**: Añade máquinas para más workers  
✅ **Recuperable**: Si falla un batch, solo reinicia ese  
✅ **Local**: No depende de APIs externas  

## Monitoreo avanzado

```bash
# Ver velocidad en tiempo real (PDFs/hora)
watch -n 60 'tail -5 indexar_paralelo.log && echo "" && ps aux | grep indexar | grep -v grep | wc -l'

# Ver uso de CPU/RAM
watch -n 5 'ps aux | grep python | grep indexar | awk "{print \$3, \$4}" | sort -rn'
```

## Si falla un batch

```bash
# Ver logs de batch específico
tail -100 indexar_paralelo.log | grep "BATCH 3"

# Reiniciar solo ese batch manualmente
python3 indexar.py --provider local --model all-mpnet-base-v2 \
  --chunk-size 1024 --pdf-dir outputs/pdfs/pdfs2/nombre_especie
```

## Resultado final

El índice completo estará en `outputs/rag_index/` con:
- ~42K PDFs indexados
- ~500K-1M chunks (depende de contenido)
- Listo para RAG queries

---

**Tiempo estimado: 10-15 días**  
**Inicio recomendado: Viernes tarde para dejar corriendo el fin de semana**
