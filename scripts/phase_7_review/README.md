# Tablero de revisión manual de parámetros (fase 7)

Resuelve el hallazgo central de [COMPARACION_BUSQUEDAS.md](../../COMPARACION_BUSQUEDAS.md):
cuando dos búsquedas rellenan la misma celda, discrepan en ~25 % de los casos. Este
tablero pone esas celdas frente a un revisor humano, con el RAG como asistente.

```bash
./scripts/phase_7_review/run_review.sh          # → http://127.0.0.1:8600
```

## Publicarlo con ngrok

El tablero escucha en **8600**. Sin contraseña queda abierto a quien alcance el
puerto: puede escribir decisiones y disparar consultas RAG, que **gastan créditos
de API**. Por eso, para exponerlo:

```bash
# 1. Servidor protegido (usuario por defecto: revisor)
REVIEW_PASSWORD='la-que-elijas' ./scripts/phase_7_review/run_review.sh

# 2. Túnel — el puerto es 8600, no 80
ngrok config add-authtoken <tu-authtoken>       # una sola vez
ngrok http 8600 --url https://ragasistent.ngrok-free.app
```

El usuario se cambia con `REVIEW_USER`. Sin `REVIEW_PASSWORD` el servidor arranca
igual pero avisa por consola de que no debe publicarse.

Quien entre desde fuera comparte los mismos `decisions.json` y caché RAG: el campo
«revisor» de cada decisión es lo único que distingue quién hizo qué.

## Qué entra a la cola

De las **538 celdas** (especie × parámetro) con valor en al menos una de las cinco
búsquedas comparables (B1, B3, B4, B5, **B6**):

| | celdas | trato |
|---|---:|---|
| Acuerdo (≥2 búsquedas, difieren ≤10 %) | 64 | se consolidan solas |
| Sin corroborar (una sola búsqueda, incluida B6) | 16 | pasan marcadas |
| **Discrepan** | **27** | cola de revisión |
| **Sin respaldo de B6** | **431** | cola de revisión, etiqueta propia |

A esas se suman dos canales que no vienen de las búsquedas: las **sugerencias de
IA** (748 celdas, inferencia taxonómica con cita) y los **registros de FishBase**
(2 344 celdas, valores curados con su referencia primaria). Se filtran por
separado y nunca se mezclan entre sí — ver «Los cuatro canales».

Dos tipos de celda entran a revisión, y se filtran por separado en la interfaz:

- **Discrepan** — dos o más búsquedas dan valores distintos (numérico: dispersión
  relativa > 10 %; categórico: cadenas distintas).
- **Sin respaldo de B6** — otra búsqueda afirma un valor y B6, la única corrida
  que adjunta unidad, base, fuente y cita textual, no encontró nada en el corpus
  para esa especie y parámetro. **No es simple falta de corroboración:** en una
  muestra de 12 celdas así, en 10 el paso de extracción declara explícitamente que
  el corpus no contiene dato alguno de la especie, y en las 2 restantes B5 había
  convertido bordes de clases de talla o tamaños de muestra en parámetros
  biológicos. 190 de las 431 son `IsMigratory`, el bloque que B5 rellenó por
  conocimiento general.

**B6 manda en el consenso.** Cuando B6 tiene valor, es el sugerido: es el único
verificable contra una cita. **B5 no vota cuando repite a B4** (partió de su CSV).

### «Sin respaldo» es una afirmación sobre la procedencia, no sobre la verdad

Que B6 no halle evidencia significa que **el corpus no lo dice**, no que el valor
sea falso. Hay parámetros que estos papers no pueden sostener por su alcance: la
condición migratoria de un ave playera está en la literatura ornitológica, no en
un corpus de ecología marina del Golfo. *Calidris mauri* es el caso: B5 lo marcó
como migratoria sin evidencia —el mismo mecanismo que en otras especies inventó
valores ajenos— y resulta ser correcto.

Por eso la decisión admite **fuente `externo` con referencia obligatoria**
(FishBase, Birds of the World, IUCN, un DOI…). Esas celdas salen al export con
estado `revisado_fuente_externa` y su referencia en columna propia, así que el
modelador distingue tres cosas distintas: respaldado por el corpus, respaldado
fuera del corpus, y sin respaldo de ningún tipo.

**Los rangos de B6 discriminan.** Cuando B6 reporta un intervalo, la interfaz marca
si el valor de cada otra búsqueda cae dentro o fuera. Ejemplo real — *Albula sp.*,
talla media: B1/B4/B5 = 24.85, B3 = 22.2, y el rango documentado de B6 es 22.2–27.5,
así que las cinco son compatibles y lo que parecía conflicto no lo es.

## Flujo de trabajo

1. **Portada** — KPIs y una tarjeta por grupo funcional, ordenadas por severidad.
   Cada tarjeta muestra conflictos, composición por severidad y pendientes.
2. **Grupo** — filtros por parámetro, severidad, estado de revisión, texto libre y
   «★ parámetros clave» (los que Atlantis necesita: mortalidad natural, edad de
   primera madurez, biomasa, crecimiento, edad máxima).
3. **Celda** — al abrirla se ve el valor de cada búsqueda con sus citas, el consenso
   sugerido y las advertencias del caso (herencia B4→B5, riesgo de `IsMigratory`).
4. **Asistencia RAG** — «Consultar RAG» lanza una consulta en vivo contra el índice
   con un prompt de auditoría: obliga a citar el fragmento o a responder
   `NO EVIDENCE IN CORPUS`, y a señalar conversiones de unidad o diferencias de
   etapa de vida que expliquen la discrepancia. Respuesta en 5–30 s; se cachea por
   celda **y motor** en `outputs/review/rag_evidence.json`. Admite pregunta libre y
   una segunda opinión con el otro motor.
5. **Decisión** — valor final, fuente (B1/B3/B4/B5, RAG, manual), revisor y
   comentario. Tres salidas: *Aceptar*, *Falta evidencia*, *Descartar celda*.

## Los cuatro canales, y por qué están separados

La cola mezcla celdas de cuatro procedencias distintas. La interfaz las mantiene
distinguibles en todo momento —insignia propia, caja propia, descargo propio—
porque el valor de este tablero está justamente en no confundirlas:

| Canal | Qué es | Qué hay que verificar |
|---|---|---|
| `conflicto` | Dos o más búsquedas del corpus discrepan | Cuál de los valores es correcto |
| `sin_respaldo` | Una búsqueda lo afirma y B6 no lo halló en el corpus | Si el valor existe en algún lado |
| `sugerencia_ia` | **Inferencia taxonómica del modelo.** No sale de ningún registro | Que la cita sostenga la afirmación biológica |
| `fishbase` | **Registro de una base curada.** Alguien lo midió y lo publicó | La referencia primaria, la especie y las unidades |

La distinción entre los dos últimos es la que más fácil se pierde y la más cara
de perder. `sugerencia_ia` es una hipótesis que dedujo el modelo; `fishbase` es
un dato que alguien midió. Por eso la caja de IA lleva borde punteado y la de
FishBase borde continuo: se ven distintas antes de leer una palabra.

### Cómo se generan

```bash
# Sugerencias taxonómicas (IsMigratory), con cita académica verificable
python3 scripts/phase_7_review/ai_suggestions.py --top-groups 60

# Snapshot de FishBase — sólo la primera vez, o para actualizar versión
python3 scripts/phase_7_review/fishbase_suggestions.py --download

# Valores numéricos de FishBase, con su referencia primaria
python3 scripts/phase_7_review/fishbase_suggestions.py

# Reconstruir la cola con ambos canales dentro
python3 scripts/phase_7_review/build_review_queue.py
```

### De dónde sale FishBase

Del snapshot público en parquet que consume hoy `rfishbase`, servido por Source
Cooperative (`cboettig/fishbase/fb/v24.07/parquet`). Se descarga a
`data/external/fishbase/` (33 MB, fuera de git) y se consulta en local: las
consultas son reproducibles y no dependen de que un servicio esté en pie. Es
además la única vía viva — la API histórica de FishBase ya no existe, el espejo
de rOpenSci está caído y las páginas web están tras un desafío de Cloudflare.

Los ocho parámetros que cubre, y de qué tabla salen:

| Parámetro | Tabla · columna | Agregación |
|---|---|---|
| `Lmax` | `species.Length` | valor curado único |
| `mean_body_size` | `species.CommonLength` | valor curado único |
| `max_age` | `species.LongevityWild` | valor curado único |
| `natural_mortality` | `popgrowth.M` | mediana de los registros |
| `growth_rate` | `popgrowth.K` | mediana de los registros |
| `age_first_maturity` | `maturity.tm` | mediana de los registros |
| `Von_bertalanffy_a` | `poplw.a` | mediana · **convención ambigua** |
| `Von_bertalanffy_b` | `poplw.b` | mediana · **convención ambigua** |

Donde hay varios registros (varios stocks, sexos y localidades) se propone la
mediana y se muestran el número de registros y el rango observado: un solo
número escondería esa dispersión.

> **Aviso sobre `Von_bertalanffy_a/b`.** La columna del CSV base está usada hoy
> con al menos tres convenciones incompatibles a la vez: hay valores que son L∞
> (427.66), otros que son la *a* de longitud–peso (2e-06) y otros que son t₀
> (-0.26); y varios `Von_bertalanffy_b` coinciden exactamente con `growth_rate`,
> o sea que ahí se guardó K. FishBase aporta la relación longitud–peso
> (W = a·L^b), que es lo que Atlantis llama `li_a`/`li_b`. Todas estas
> sugerencias salen con confianza **baja** y con el aviso escrito: hay que
> decidir qué mide el campo antes de aceptar ninguna.

## Archivos

| Ruta | Qué es |
|---|---|
| `build_review_queue.py` | Construye la cola comparando los CSV y fusionando los dos canales de sugerencia |
| `ai_suggestions.py` | Sugerencias taxonómicas de IsMigratory, con cita verificable |
| `fishbase_suggestions.py` | Descarga el snapshot de FishBase y emite sugerencias numéricas |
| `review_server.py` | API FastAPI + servidor estático |
| `static/` | Interfaz (HTML/CSS/JS sin dependencias) |
| `outputs/review/review_queue.json` | La cola (regenerable) |
| `outputs/review/decisions.json` | Decisiones del revisor, con historial |
| `outputs/review/rag_evidence.json` | Caché de consultas RAG por celda |
| `outputs/review/ai_suggestions.json` | Sugerencias taxonómicas (regenerable) |
| `outputs/review/fishbase_suggestions.json` | Sugerencias de FishBase (regenerable) |
| `data/external/fishbase/*.parquet` | Snapshot de FishBase, fuera de git (regenerable con `--download`) |
| `outputs/review/Atlantis_GOC_parametros_consolidado.csv` | Export: mismo esquema de 24 columnas que las búsquedas |
| `outputs/review/Atlantis_GOC_procedencia.csv` | Export: una fila por celda con estado, nº de búsquedas, dispersión y revisor |

El botón **Exportar CSV** fusiona las cuatro búsquedas aplicando las decisiones:

| status en procedencia | origen del valor |
|---|---|
| `revisado` | decisión del revisor |
| `descartado` | celda vaciada por el revisor |
| `conflicto_pendiente` | consenso provisional, aún sin revisar |
| `conflicto_sin_consenso` | empate categórico: celda vacía, requiere decisión |
| `acuerdo` | mediana / valor común |
| `sin_corroborar` | única búsqueda que lo reportó |
| `sin_respaldo_b6` | otras búsquedas lo afirman, B6 no halló evidencia; el valor se conserva marcado |
| `revisado_fuente_externa` | el revisor lo respaldó con una fuente ajena al corpus (columna `reference`) |

## Notas técnicas

- Este servidor **no toca** `scripts/phase_6_query/server_rag_api.py`; la
  inicialización del motor está copiada para poder evolucionar por separado.
- Modelo de la asistencia: `claude-sonnet-5`, `thinking` desactivado, `top_k=10`.

### Los dos motores: por qué el semántico es el predeterminado

El índice BM25 ya está construido (`scripts/build_bm25_index.py`, 18 080 chunks),
así que ambos motores están disponibles:

| motor | recuperación |
|---|---|
| `semantic` (**predeterminado**) | FAISS puro — el mismo que corrió B1–B5 |
| `hybrid` | FAISS + BM25 fusionados por RRF (+ canal de tablas si existe) |

Comparación sobre 6 celdas en conflicto (los 3 críticos y los numéricos de mayor
dispersión), **mismo prompt de auditoría y mismo modelo en ambos**: coinciden en 5
de 6 y tardan lo mismo. En la sexta el híbrido pierde: para
`Micropogonias megalops · biomass_mt`, el semántico recupera la Tabla 1 de
Herrera2015 p.4 y dictamina que 140 768.9 g = 140.77 kg = 0.1408 t (los cuatro
valores son el mismo dato mal convertido); el híbrido coloca en su lugar un
Lopez2021 sobre biomasa de almejas —match léxico de «biomass»— y responde
`NO EVIDENCE IN CORPUS`.

Seis casos no son un benchmark, pero como el híbrido no aportó ninguna ventaja en
la muestra y sí desplazó el fragmento decisivo en un caso, el predeterminado es el
semántico y el híbrido queda a un clic como **segunda opinión**. Las respuestas de
ambos se guardan por separado, así que la comparación se puede ampliar sobre la
marcha.
- La cola se puede regenerar en cualquier momento (`REBUILD=1`); las decisiones
  siguen ligadas a la celda por `fila:parámetro`, así que sobreviven.
