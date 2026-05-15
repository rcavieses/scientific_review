# PASO 3 y 4 en Ejecución

## 📊 Estado Actual

```
PASO 3: Buscar artículos científicos
├─ Consultando: PubMed, CrossRef, ArXiv
├─ Especies: 3,814 MARINE
├─ Estado: EN PROGRESO
└─ Tiempo estimado: 1-2 horas (depende de APIs)

PASO 4: Descargar PDFs
├─ Basado en DOIs y URLs de Paso 3
├─ Estado: PENDIENTE (se ejecutará después del Paso 3)
└─ Tiempo estimado: Variable (según cantidad de archivos)
```

---

## 🔍 Qué está pasando

### PASO 3: search_articles.py

El script está:
1. **Leyendo** la lista de 3,814 especies marinas de `species_acuaticas.csv`
2. **Buscando** en:
   - **PubMed** (NCBI): articulos biomédicos sobre especies
   - **CrossRef**: artículos con DOI (Digital Object Identifier)
   - **ArXiv**: preprints científicos
3. **Guardando** resultados en:
   - `search_results/{especie}.csv` (20 artículos máx por especie)
4. **Removiendo** duplicados por título
5. **Rastreando** progreso en `search_progress.json`

**Velocidad**: ~1 artículo cada 1-2 segundos (respetando rate limits de APIs)

### Cálculo de Tiempo

- 3,814 especies × 1-2 seg/especie = 1-2 horas aprox
- Pero muchas especies no tendrán resultados (más rápido)
- Promedio observado: 3-8% de especies con artículos

---

## 📁 Archivos Generados

### Mientras se ejecuta:

```
search_results/
├── species_1.csv         ← Artículos para "species 1"
├── species_2.csv         ← Artículos para "species 2"
└── ...

search_progress.json      ← Tracking de progreso
```

### Estructura de CSV:

```csv
source,title,authors,year,journal,doi,url,pubmed_id,arxiv_id
PubMed,"Study of species X","Smith J., et al",2023,"Journal Name","10.1234/..","https://..","12345678",
CrossRef,"Research on Y","Doe A.,...",2022,"Nature","10.5678/..","https://..","","
ArXiv,"Preprint about Z","Lee B.",2024,"ArXiv","","https://..","","2401.12345"
```

---

## 🔄 Monitorear Progreso

### Opción 1: Ver logs en tiempo real
```bash
tail -f search_progress.json | python3 -m json.tool
```

### Opción 2: Ver archivos generados
```bash
ls -lah search_results/ | head -20
wc -l search_results/*.csv | tail -1
```

### Opción 3: Contar resultados
```bash
find search_results -name "*.csv" | wc -l
```

---

## ⏸️ Si Necesitas Pausar

```bash
pkill -f search_articles.py
# El progreso se guarda en search_progress.json
# Puedes reanudar ejecutando nuevamente:
python3 search_articles.py
```

---

## ✅ Cuándo esté Completo

1. **search_progress.json** estará completo (3,814 entradas)
2. **search_results/** contendrá CSVs para cada especie
3. Automáticamente se ejecutará **PASO 4**: Descargar PDFs

---

## 📥 PASO 4: download_pdfs.py

Una vez complete el Paso 3, se ejecutará automáticamente:

```python
# Intenta descargar desde (en orden):
1. DOI resolver (doi.org)
2. ArXiv PDFs (si tiene arxiv_id)
3. URLs directas (links en artículos)
4. PubMed full text (si tiene pubmed_id)
```

Almacena en:
```
pdfs/{especie}/
├── PubMed_articulo1.pdf
├── CrossRef_articulo2.pdf
└── ArXiv_articulo3.pdf
```

---

## 🎯 Resumen Total

```
PASO 1: ✅ Completado (3,814 especies MARINE)
PASO 2: ✅ Completado (filtrado)
PASO 3: 🔄 EN PROGRESO (búsqueda de artículos)
PASO 4: ⏳ PENDIENTE (descarga de PDFs)
PASO 5: ⏳ PENDIENTE (indexación RAG)
PASO 6: ✅ Completado (reporte)
```

---

## 💡 Tips

- Si necesitas ver el progreso más frecuentemente:
  ```bash
  watch -n 5 'wc -l search_results/*.csv | tail -1'
  ```

- Para ver qué especies se procesaron:
  ```bash
  head -20 search_progress.json
  ```

- Para ver primeros resultados:
  ```bash
  head -5 search_results/*.csv | head -20
  ```

---

## 📞 Próximos Pasos

1. Espera a que complete Paso 3 (1-2 horas)
2. Paso 4 (descarga) se ejecutará automáticamente
3. Verifica PDFs descargados en `pdfs/`
4. Los archivos estarán listos para indexación RAG

