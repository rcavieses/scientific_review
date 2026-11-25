# Comparación de las 5 búsquedas de parámetros poblacionales (RAG · Atlantis GOC)

Documento generado el 2026-08-16 a partir de los CSV, los JSON de progreso y los
logs de ejecución del repositorio. Todas las cifras son reproducibles con
[scripts/compare_busquedas_figures.py](scripts/compare_busquedas_figures.py);
las tablas fuente quedan en
[outputs/reports/comparacion_busquedas/](outputs/reports/comparacion_busquedas/).

**Universo evaluado:** 1 122 especies de vertebrados, 51 grupos funcionales,
14 parámetros poblacionales → 15 708 celdas posibles por búsqueda.
**Índice RAG:** 18 080 chunks (idéntico en las cinco ejecuciones).

---

## 1. Qué fue cada búsqueda

| # | Fecha | Modelo LLM | Alcance ejecutado | Estrategia / cambio respecto a la anterior | Salida |
|---|-------|-----------|-------------------|--------------------------------------------|--------|
| **B1** | 2026-08-12 | Haiku 4.5 | 51 grupos | Línea base: consulta dual (extracción + mapeo a esquema), `top_k=10`, extracción de citas | `..._BUSQUEDA1.csv` |
| **B2** | 2026-08-12 | Haiku 4.5 | — | Réplica **idéntica** a B1 para medir reproducibilidad. **Sin CSV conservado**: solo existe `outputs/busqueda2_metadata.json` | — |
| **B3** | 2026-08-12 | Haiku 4.5 | 51 grupos | Reejecución con prompts ajustados; misma arquitectura dual | `..._BUSQUEDA_3.csv` |
| **B4** | 2026-08-12/13 | Haiku 4.5 | 51 grupos | Refactor operativo: bucle sobre **todos** los grupos, guardado de progreso por grupo y `continue` ante error (antes el script moría en el primer grupo) | `..._BUSQUEDA_4.csv` |
| **B5** | 2026-08-15 | **Claude Sonnet 5** (`thinking: disabled`, `max_tokens=4096`) | 51 grupos | Cambio de modelo; se añadió soporte de `thinking` en `AnthropicProvider` y `RAGQueryEngine`. Partió del CSV de B4 | `..._BUSQUEDA_5.csv` |

> **Aviso metodológico 1 — B2 no es comparable.** Su único rastro es el archivo de
> metadatos; el CSV nunca se guardó con nombre propio, así que la prueba de
> reproducibilidad que se pretendía con ella no puede evaluarse. Todo lo que sigue
> compara B1, B3, B4 y B5.
>
> **Aviso metodológico 2 — B5 es acumulativa.** B5 escribió sobre una copia del CSV
> de B4 y `update_csv_row()` solo sobrescribe cuando el modelo devuelve un valor no
> nulo. En consecuencia, las 242 celdas de B4 están **contenidas al 100 %** en B5
> (0 celdas exclusivas de B4). La ganancia limpia atribuible a Sonnet 5 son las
> **188 celdas nuevas**, no las 430 totales.

---

## 2. Rendimiento global

![Rendimiento global por búsqueda](outputs/reports/comparacion_busquedas/fig1_rendimiento_global.png)

| Métrica | B1 | B3 | B4 | B5 |
|---|---:|---:|---:|---:|
| Valores extraídos (celdas) | 237 | 266 | 242 | **430** |
| Cobertura sobre 15 708 celdas | 1,51 % | 1,69 % | 1,54 % | **2,74 %** |
| Especies con ≥1 parámetro | 92 | 104 | 92 | **232** |
| Cobertura de especies (de 1 122) | 8,2 % | 9,3 % | 8,2 % | **20,7 %** |
| Especies sin información | 1 030 | 1 027 | 1 030 | **914** |
| Parámetros por especie hallada (media) | 2,58 | 2,56 | 2,63 | 1,85 |
| Especies con cita bibliográfica | 90 | 99 | 89 | 221 |
| Especies con dato **sin** cita | 2 | 5 | 3 | **11** |
| Errores registrados | 0 | 0 | 0 | 0 |

B5 duplica la cobertura de especies, pero con **menos densidad por especie**
(1,85 vs ~2,6 parámetros): gana amplitud a base de rellenar un único campo en
muchas especies nuevas — casi siempre `IsMigratory` (§4).

---

## 3. Cobertura por parámetro

![Especies con dato, por parámetro y búsqueda](outputs/reports/comparacion_busquedas/fig2_heatmap_parametros.png)

| Parámetro | B1 | B3 | B4 | B5 | Δ B5–B4 |
|---|---:|---:|---:|---:|---:|
| IsMigratory | 32 | 45 | 36 | 184 | **+148** |
| mean_body_size | 44 | 47 | 45 | 51 | +6 |
| abundance_numbers | 38 | 41 | 37 | 48 | +11 |
| Lmax | 43 | 45 | 41 | 47 | +6 |
| StartSpawnDayOfYear | 16 | 18 | 19 | 21 | +2 |
| EndSpawnDayOfYear | 16 | 18 | 19 | 21 | +2 |
| Von_bertalanffy_b | 12 | 12 | 11 | 13 | +2 |
| growth_rate | 7 | 6 | 6 | 12 | +6 |
| max_age | 8 | 8 | 9 | 11 | +2 |
| Von_bertalanffy_a | 8 | 7 | 9 | 9 | 0 |
| biomass_mt | 5 | 9 | 4 | 6 | +2 |
| natural_mortality | 3 | 4 | 4 | 5 | +1 |
| larval_duration | 5 | 5 | 1 | 1 | 0 |
| age_first_maturity | 0 | 1 | 1 | 1 | 0 |

Lectura:

- Los parámetros **más críticos para Atlantis** siguen prácticamente vacíos en las
  cinco corridas: `natural_mortality` (≤5 especies), `age_first_maturity` (≤1),
  `biomass_mt` (≤9). Ninguna búsqueda mueve la aguja aquí.
- `larval_duration` **retrocede** de 5 (B1/B3) a 1 (B4/B5): B4 no reprodujo cuatro
  hallazgos previos y B5, al heredar el archivo de B4, tampoco los recuperó.
- Excluyendo `IsMigratory`, la ganancia total de B5 sobre B4 es de **+40 celdas**
  (206 → 246), un +19 %, no el +78 % que sugiere el agregado.

---

## 4. El caso `IsMigratory`

| | B1 | B3 | B4 | B5 |
|---|---:|---:|---:|---:|
| Especies con valor | 32 | 45 | 36 | 184 |
| `yes` | 15 | 28 | 21 | **162** |
| `no` | 17 | 17 | 15 | 22 |
| Proporción `yes` | 47 % | 62 % | 58 % | **88 %** |

El salto de 36 → 184 con un sesgo de 88 % hacia `yes` es el resultado más
llamativo y el más sospechoso. Es un campo booleano que un LLM puede "deducir"
del conocimiento general del taxón sin que el contexto RAG lo respalde, y el
grupo que más crece es *Surface-feeding Seabirds* (7 → 83 especies, §5), donde la
migración es una asunción por defecto plausible. **Recomendación: auditar
manualmente una muestra de `IsMigratory=yes` de B5 contra su campo `citations`
antes de aceptar esos 148 valores nuevos.**

---

## 5. Cobertura por grupo funcional

![Cobertura por grupo funcional](outputs/reports/comparacion_busquedas/fig4_grupos_funcionales.png)

| Grupo funcional | n especies | B1 | B3 | B4 | B5 |
|---|---:|---:|---:|---:|---:|
| Surface-feeding Seabirds | 172 | 7 | 16 | 7 | **83** |
| Reef Carnivores | 217 | 18 | 15 | 16 | 20 |
| Other Demersal Fish | 174 | 13 | 18 | 15 | 17 |
| Piscivorous Seabirds | 28 | 2 | 3 | 3 | 12 |
| Diving Seabirds | 56 | 1 | 1 | 2 | 12 |
| Coastal Planktivores | 53 | 6 | 8 | 5 | 9 |
| Flatfish | 45 | 7 | 7 | 8 | 8 |
| Snappers | 12 | 6 | 6 | 7 | 7 |
| Lanternfish and Deep | 67 | 5 | 6 | 4 | 6 |
| Large sharks and rays | 9 | 4 | 4 | 3 | 5 |
| Other Tunas | 10 | 0 | 2 | 1 | 5 |
| Large Pelagic fish | 25 | 0 | 0 | 1 | 4 |

Toda la ventaja de B5 se concentra en las **aves marinas** (+107 especies entre los
tres grupos de *Seabirds*), coherente con el efecto `IsMigratory`. En los grupos de
peces —donde están los parámetros que el modelo Atlantis realmente necesita— las
cuatro búsquedas son estadísticamente equivalentes (±3 especies).

---

## 6. Reproducibilidad y estabilidad de los valores

![Reproducibilidad entre pares de búsquedas](outputs/reports/comparacion_busquedas/fig3_reproducibilidad.png)

| Par | Jaccard de celdas | Valor idéntico en celdas comunes |
|---|---:|---:|
| B1–B3 | 52,9 % | 76,4 % |
| B1–B4 | 52,1 % | 76,2 % |
| B1–B5 | 38,1 % | 74,5 % |
| B3–B4 | 51,2 % | 68,6 % |
| B3–B5 | 42,6 % | 69,7 % |
| B4–B5 | 56,3 % | 85,1 % (inflado: B5 hereda B4) |

Divergencia numérica sobre los campos cuantitativos (comparando el primer número
de cada celda):

| Par | Celdas numéricas comparables | Idénticas | Difieren >10 % | Difieren >100 % |
|---|---:|---:|---:|---:|
| B1–B3 | 154 | 114 (74 %) | 29 | 3 |
| B1–B4 | 150 | 112 (75 %) | 23 | 6 |
| B3–B5 | 170 | 116 (68 %) | 35 | 11 |
| B4–B5 | 206 | 173 (84 %) | 24 | 8 |

**Este es el hallazgo más importante del análisis.** Con configuración esencialmente
equivalente (B1, B3, B4 · mismo modelo, mismo índice), dos corridas coinciden en
apenas **la mitad de las celdas** que rellenan, y cuando ambas rellenan la misma
celda discrepan en **~25 % de los casos**, con un puñado de discrepancias de más de
un orden de magnitud. El pipeline no es determinista a nivel de resultado útil: una
sola corrida no es una medición, es una muestra.

---

## 7. Composición de la unión

![Composición de la unión de las 4 búsquedas](outputs/reports/comparacion_busquedas/fig5_union_valores.png)

| Segmento | Valores |
|---|---:|
| Núcleo estable (presente en las 4 búsquedas) | 148 |
| Parcial (en 2 o 3 búsquedas) | 162 |
| Solo B1 | 34 |
| Solo B3 | 39 |
| Solo B4 | 0 (subconjunto de B5) |
| Solo B5 | 139 |
| **Unión total** | **522 valores · 255 especies** |

La unión de las cuatro búsquedas (522 celdas, 255 especies, 22,7 % del padrón) supera
en 21 % a la mejor búsqueda individual (430). Solo **148 valores (28 %)** aparecen en
las cuatro: ese núcleo es el subconjunto en el que se puede confiar sin revisión
manual.

---

## 8. Coste operativo

| | B4 (Haiku 4.5) | B5 (Sonnet 5) |
|---|---|---|
| Inicio → fin | 2026-08-12 23:00 → 2026-08-13 01:04 | 2026-08-15 01:10 → 04:58 |
| Duración | **2 h 04 min** | **3 h 48 min** (+84 %) |
| Llamadas a la API | 2 245 | 2 250 (2 por especie: extracción + mapeo) |
| Celdas nuevas aportadas | — | +188 (de ellas 148 son `IsMigratory`) |
| Errores | 0 | 0 |

B1 y B3 escribieron en el log compartido `rag_parameter_completion.log`, por lo que su
duración no puede aislarse con fiabilidad.

Sonnet 5 cuesta ~1,8× más tiempo de reloj (y notablemente más por token) para
entregar, fuera de `IsMigratory`, **+40 celdas**: ~1 celda adicional de valor
verificable por cada 5,5 minutos extra de ejecución.

---

## 9. Conclusiones y recomendaciones

1. **Ninguna búsqueda es suficiente por sí sola.** La mejor cubre 20,7 % de las
   especies y 2,7 % de las celdas; la unión de las cuatro llega a 22,7 % / 3,3 %.
   El cuello de botella no es el LLM, es la cobertura documental del corpus.
2. **Consolidar por unión, no elegir un ganador.** Fusionar B1+B3+B4+B5 con
   resolución de conflictos por votación (y revisión manual donde haya empate o
   discrepancia >10 %) es la salida de mayor valor disponible hoy.
3. **B5 está sobrevalorada por su métrica agregada.** Su ventaja real sobre B4, una
   vez descontados el arrastre del archivo heredado y el bloque de `IsMigratory`,
   es de +40 celdas al doble de coste temporal.
4. **Auditar `IsMigratory` de B5** antes de integrarlo: 148 valores nuevos, 88 %
   `yes`, concentrados en aves marinas; alto riesgo de conocimiento paramétrico del
   modelo en lugar de evidencia del corpus.
5. **Reparar la trazabilidad del experimento.** B2 se perdió por no versionar su CSV
   y B5 contaminó su comparación al escribir sobre el archivo de B4. Regla para
   futuras corridas: cada búsqueda parte de un CSV **vacío** y guarda salida, log y
   metadatos con nombre propio.
6. **Tratar la variabilidad como parte del diseño.** Con ~25 % de discrepancia entre
   corridas equivalentes, el protocolo debería ser *n* réplicas + consenso, y no una
   pasada única. Tres réplicas del mismo modelo probablemente rindan más que una
   pasada con un modelo más caro.
7. **Atacar el cuello real:** `natural_mortality`, `age_first_maturity` y
   `biomass_mt` siguen esencialmente vacíos tras cinco intentos. Ahí el camino no es
   otro prompt, sino otras fuentes (FishBase, ya implementado en
   [scripts/fishbase_population_fetcher.py](scripts/fishbase_population_fetcher.py))
   o más PDFs indexados.

---

### Archivos de apoyo

| Archivo | Contenido |
|---|---|
| [outputs/reports/comparacion_busquedas/cobertura_por_parametro.csv](outputs/reports/comparacion_busquedas/cobertura_por_parametro.csv) | Matriz parámetro × búsqueda |
| [outputs/reports/comparacion_busquedas/cobertura_por_grupo.csv](outputs/reports/comparacion_busquedas/cobertura_por_grupo.csv) | Los 51 grupos funcionales |
| [outputs/reports/comparacion_busquedas/reproducibilidad.csv](outputs/reports/comparacion_busquedas/reproducibilidad.csv) | Jaccard y concordancia por par |
| [outputs/reports/comparacion_busquedas/solapamiento.csv](outputs/reports/comparacion_busquedas/solapamiento.csv) | Intersección/unión por par |
| [scripts/compare_busquedas_figures.py](scripts/compare_busquedas_figures.py) | Script que regenera tablas y figuras |
