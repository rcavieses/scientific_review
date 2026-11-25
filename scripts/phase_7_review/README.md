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
IA** (748 celdas, inferencia taxonómica con cita) y el **reparto de esquema**
(25 celdas). FishBase se revisa aparte, en su propia página.

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

## Los seis canales de la cola, y por qué están separados

La cola mezcla celdas de seis procedencias distintas. La interfaz las mantiene
distinguibles en todo momento —insignia propia, caja propia, descargo propio—
porque el valor de este tablero está justamente en no confundirlas:

| Canal | Qué es | Qué hay que verificar |
|---|---|---|
| `conflicto` | Dos o más búsquedas del corpus discrepan | Cuál de los valores es correcto |
| `sin_respaldo` | Una búsqueda lo afirma y B6 no lo halló en el corpus | Si el valor existe en algún lado |
| `sugerencia_ia` | **Inferencia taxonómica del modelo.** No sale de ningún registro | Que la cita sostenga la afirmación biológica |
| `reclasificado` | **Valor que ya existía, en la columna equivocada.** No es dato nuevo | Que la cantidad sea la que dice el reparto |
| `peso_talla` | **Extracción dirigida sobre el corpus**, con cita textual, tras corregir la definición de `li_a`/`li_b` | Que la cita sea de esta especie y traiga las unidades de W y L |
| `notebooklm` | **Literatura que el índice FAISS no tiene**, leída por dos notebooks de NotebookLM y reconciliada entre ambos | Que la cita nombre un documento real, y —si los notebooks discrepan— cuál de los dos aplica al Golfo |

FishBase **no** está en esta lista: tiene página propia. Ver más abajo.

### Validación por respaldo regional de las sugerencias de IA

El mismo criterio que se aplica a FishBase, sobre una cosa distinta. FishBase se
valida cuando el registro **se midió** en la región; una sugerencia de IA no
tiene medición, así que lo que se clasifica es **su cita**:

    FishBase validado  →  «este valor se midió en el Golfo».
    IA validada        →  «esta afirmación biológica la sostiene literatura del
                           Golfo; el valor sigue siendo una inferencia
                           taxonómica, no un dato medido».

De ahí que salgan con estado propio, `validado_region_cita`, y no se mezclen
con `validado_region`: quien quiera sólo mediciones filtra por estado y no se
lleva ninguna de éstas.

De las 45 referencias del catálogo de `ai_suggestions.py`, **21 son
regionales** — 17 del Golfo (Thomson 2000, Hobson 1965/1968, Sala 2003,
Nevárez 1999/2001, Erisman 2012, Rojas-Bracho 2006…), 1 del Pacífico mexicano
y 3 del Pacífico oriental. Las otras 24 sostienen afirmaciones ciertas pero
medidas en otra parte: Barbados, Nueva Zelanda, Hawái, Cuba, el Mar del Norte.

```bash
python3 scripts/phase_7_review/ai_autovalidate.py --citas     # qué cita es regional
python3 scripts/phase_7_review/ai_autovalidate.py --dry-run
python3 scripts/phase_7_review/ai_autovalidate.py --reviewer "R. Cavieses"
python3 scripts/phase_7_review/ai_autovalidate.py --deshacer
```

**Las de confianza baja no entran.** Esas reglas avisan en su propio texto de
que el campo es ambiguo para ese taxón: los mictófidos migran verticalmente y
no entre zonas; las mobulas se agregan *dentro* del Golfo. Aprobarlas en lote
sería contestar automáticamente justo la pregunta que la regla deja abierta.
Son 6 celdas (Mobulidae, Dorosomatidae) y siguen pendientes; `--incluir-baja`
las mete si se decide antes qué mide `IsMigratory`.

Las 290 sin respaldo regional tampoco entran, y por una razón distinta: la
afirmación puede ser perfectamente cierta —un gobio es sedentario en cualquier
océano— pero la literatura que la sostiene no es de aquí. Quedan a revisión
humana. Son sobre todo aves (Howell 1995 es una guía nacional, no regional),
peces planos (Able 2014, Gibson 1994) y mesopelágicos (Sutton 2013).

### Cómo se generan

```bash
# Sugerencias taxonómicas (IsMigratory), con cita académica verificable
python3 scripts/phase_7_review/ai_suggestions.py --top-groups 60

# Snapshot de FishBase — sólo la primera vez, o para actualizar versión
python3 scripts/phase_7_review/fishbase_suggestions.py --download

# Valores numéricos de FishBase, con su referencia primaria
python3 scripts/phase_7_review/fishbase_suggestions.py

# Peso-talla: recuperar li_a/li_b del corpus (ver más abajo)
python3 scripts/phase_7_review/lw_extract.py --remap     # sobre el crudo ya guardado
python3 scripts/phase_7_review/lw_extract.py --corpus    # consulta dirigida, sólo peces

# NotebookLM: preguntar a los dos notebooks por las celdas que siguen vacías
python3 scripts/phase_7_review/nblm_client.py --listar          # ids -> config
python3 scripts/phase_7_review/nblm_extract.py --dry-run --limit 1
python3 scripts/phase_7_review/nblm_extract.py

# Reconstruir la cola con todos los canales dentro
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

### Validación por procedencia

FishBase agrega estudios de todo el mundo. Para un modelo del Golfo de
California, una K medida en el Mar del Norte y otra medida en Guaymas no valen
lo mismo, aunque la tabla las liste juntas. De cada registro se lee de dónde
salió (`fb_region.py`) y se clasifica en tres niveles:

| Nivel | Qué incluye | Celdas |
|---|---|---|
| Golfo de California | golfo, Sonora, Sinaloa, Baja + golfo, Guaymas, Mazatlán… | 377 |
| Pacífico mexicano | costa oeste de Baja, Colima, Nayarit, Guerrero, Tehuantepec… | 286 |
| Pacífico oriental | corriente de California, Galápagos, Perú, Chile, Panamá… | 561 |

Dos consecuencias, y la primera importa más que la segunda:

1. **El valor cambia.** Si hay registros de la región, la mediana se calcula
   sólo con ellos; la mundial se conserva aparte (`value_global`) para poder
   comparar. Ejemplo real — *Istiophorus platypterus*: K mundial 0.29 sobre 13
   registros, K del Golfo 0.752 sobre 1. Un valor que se va a aprobar como
   validado para el Golfo tiene que salir del Golfo.
2. **La celda se puede aprobar en lote**, sin ir al paper: la procedencia ya
   contesta la pregunta que la revisión celda a celda tenía que contestar.
   Salen al export con estado `validado_region`, distinto de
   `revisado_fishbase`, y la nota lleva la localidad exacta.

**La señal no siempre vale lo mismo.** «Localidad» es dónde se midió, y es
prueba. «Referencia» es que la localidad está vacía y lo que casa es el título
del estudio: un catálogo del Pacífico oriental puede citar una talla medida en
cualquier parte, así que es indicio y **no entra en el aprobado por defecto**.
Los tres parámetros de la tabla `species` (`Lmax`, `mean_body_size`, `max_age`)
sólo se pueden clasificar así —esa tabla no guarda localidad—, de modo que en la
práctica quedan siempre para revisión humana.

Que FishBase no diga de dónde salió un dato no significa que venga de fuera de
la región: esas celdas se quedan pendientes, exactamente como estaban.

```bash
# Ver qué haría, sin escribir nada
python3 scripts/phase_7_review/fb_autovalidate.py --dry-run

# Aprobar (744 celdas con localidad regional, de las 2 771 propuestas)
python3 scripts/phase_7_review/fb_autovalidate.py --reviewer "R. Cavieses"

# Sólo lo estrictamente local, o incluyendo el indicio por título
python3 scripts/phase_7_review/fb_autovalidate.py --nivel golfo_california
python3 scripts/phase_7_review/fb_autovalidate.py --incluir-referencia

# Revertir en bloque: sólo lo que aprobó esta regla, no lo aceptado a mano
python3 scripts/phase_7_review/fb_autovalidate.py --deshacer
```

Lo mismo se hace desde el tablero, con el botón de la página de FishBase; deja
el mismo sello, así que revertirlo es una sola operación se haya hecho desde
donde se haya hecho. En la tabla, cada celda regional lleva su marca —`GC`,
`PM`, `PO`, punteada si es sólo indicio— y el tooltip trae la localidad, cuántos
registros de la región sostienen el valor y cuál habría sido la mediana mundial.

> **Aviso sobre `Von_bertalanffy_a/b`.** La columna del CSV base está usada hoy
> con al menos tres convenciones incompatibles a la vez: hay valores que son L∞
> (427.66), otros que son la *a* de longitud–peso (2e-06) y otros que son t₀
> (-0.26); y varios `Von_bertalanffy_b` coinciden exactamente con `growth_rate`,
> o sea que ahí se guardó K. FishBase aporta la relación longitud–peso
> (W = a·L^b), que es lo que Atlantis llama `li_a`/`li_b`. Todas estas
> sugerencias salen con confianza **baja** y con el aviso escrito: hay que
> decidir qué mide el campo antes de aceptar ninguna.

## El esquema de crecimiento y peso-talla

Hasta agosto de 2026 existían dos columnas, `Von_bertalanffy_a` y
`Von_bertalanffy_b`, que entre las cinco búsquedas acumularon **cuatro
cantidades distintas**: 29 valores de L∞, 6 de t₀ y 4 del coeficiente *a* de
peso-talla en `_a`; 35 de K y 19 del exponente *b* en `_b`.

**La causa fue el nombre, no la extracción.** El Excel de origen siempre dijo,
en sus columnas 13 y 14, «Coefficient a/b of the allometric length–weight
relationship» — es decir, `li_a` y `li_b`. Al generar el CSV se renombraron a
`Von_bertalanffy_a/b`, y ese nombre equivocado es el que se le pasó al
extractor: «Von Bertalanffy coefficient a» no significa nada, porque la
ecuación de von Bertalanffy tiene L∞, K y t₀, no una «a» ni una «b». Sin una
definición real, cada corrida resolvió la ambigüedad a su manera. B6 la
redefinió explícitamente como a = L∞ y b = K, lo que además dejó
`Von_bertalanffy_b` duplicando a `growth_rate`.

El esquema actual separa cada cantidad:

| Columna | Qué es | Origen |
|---|---|---|
| `li_a` | Coeficiente *a* de W = a·L^b | Columna 13 del Excel, con su nombre correcto |
| `li_b` | Exponente *b* de W = a·L^b | Columna 14 del Excel, con su nombre correcto |
| `vb_Linf` | Talla asintótica L∞ (cm) | Columna 28, nueva |
| `vb_t0` | Edad teórica a talla cero t₀ (años) | Columna 29, nueva |
| `growth_rate` | Coeficiente K (1/año) | Ya existía. **Única casa de K** |

K vive sólo en `growth_rate`: darle dos columnas fue parte del enredo original.

Los valores ya extraídos no se reescribieron: `reclassify_vb.py` los reparte a
su columna real y los manda al tablero como celdas pendientes, porque el
reparto es una lectura de la magnitud y una lectura la confirma un humano.

```bash
python3 scripts/phase_7_review/reclassify_vb.py --informe   # ver el reparto
python3 scripts/phase_7_review/reclassify_vb.py             # generarlo
```

### Dos errores que el reparto dejó a la vista

**Milímetros contra centímetros.** Cuatro celdas discrepan exactamente 10×
entre búsquedas (43.2 contra 432.32). B6 llegó a anotar «mm total length,
converted to cm (42.77)» y guardó igualmente 427.655: describió la conversión
sin aplicarla. El script propone el valor en escala cm y baja la confianza,
pero nunca lo resuelve en silencio.

**Colisión de epítetos.** Esas cuatro celdas son `Atherinops affinis`,
`Elops affinis`, `Caulolatilus affinis` y `Aythya affinis` — un pejerrey, un
machete, un blanquillo y **un pato**, intercambiándose los mismos cuatro
números porque comparten el epíteto. Es la firma del emparejamiento difuso, y
el script lo nombra explícitamente en cada celda afectada.

## Los coeficientes de peso-talla: por qué hubo que reobtenerlos

`li_a` y `li_b` salían **vacíos en el CSV consolidado: 0 valores de 1 122
especies**. No porque el corpus no los tuviera, sino porque el paso 2 de la
extracción no tenía dónde ponerlos: se le pidió «Von Bertalanffy coefficient
a/b», que no significa nada, así que un exponente alométrico no encajaba en
ningún campo y se tiraba.

El crudo del paso 1 que B6 guardó lo demuestra especie por especie:

| Especie | Lo que el corpus dice | Lo que el paso 2 guardó |
|---|---|---|
| *Triphoturus mexicanus* | `b = 2.79` | nada |
| *Benthosema panamense* | `b = 2.09` | nada |
| *Caulolatilus affinis* | `b = 2.66` | L∞ y K, sin la b |
| *Holacanthus passer* | `b = 2.618` | `0.127`, que es K |
| *Hoplopagrus guentherii* | `W = a × Lt^b`, n = 282 | nada |

`lw_extract.py` los recupera en dos fases, ambas dirigidas **sólo** a peso-talla:

| Fase | Qué hace | Coste |
|---|---|---|
| `--remap` | Vuelve a mapear los 37 crudos del paso 1 que B6 alcanzó a guardar, con la definición correcta. **No recupera nada del índice**: el texto ya estaba extraído | 37 llamadas, ~3 min |
| `--corpus` | Una consulta por especie al índice, únicamente sobre W = a·L^b | ~800 llamadas, ~1 h |

**Sólo peces.** `--corpus` filtra por `Class` a Teleostei, Actinopterygii y
Chondrichthyes. W = a·L^b no aplica a aves ni mamíferos, y es justo ahí donde
el emparejamiento difuso metió valores ajenos: *Aythya affinis* —un pato—
heredó la `b = 2.66` de *Caulolatilus affinis* por compartir epíteto.

### Las tres guardas, y por qué cada una

1. **Rango de plausibilidad.** `b` fuera de 2–4.5 y `a` fuera de 1e-9–1 se
   descartan con el motivo escrito. Aceptar callado un número que no puede ser
   lo que dice ser es exactamente como `Von_bertalanffy_a` se llenó de L∞ y t₀.
2. **Cita obligatoria.** Sin fragmento verbatim no hay sugerencia. Un valor sin
   cita no se puede comprobar, y este canal existe precisamente para poder.
3. **Comprobación de género.** Si la cita nombra el epíteto pero no el género,
   la sugerencia baja a confianza **baja** y lo dice. En el re-mapeo esta guarda
   ya funcionó: el modelo devolvió `null` para *Aythya affinis* con la nota
   «all data are for *Caulolatilus*».

Nada de esto se escribe en ningún CSV. Salen a
`outputs/review/lw_suggestions.json` y entran a la cola como canal
`peso_talla`, porque una cita hay que leerla.

### Lo que el barrido encontró, y lo que eso significa

Corridas las dos fases —37 re-mapeos y 783 consultas al corpus, una por pez—:

| | li_a | li_b |
|---|---:|---:|
| Recuperado del corpus | **0** | **7** |
| Propuesto por FishBase | 425 | 420 |

Las siete: *Benthosema panamense* 2.09, *Brotula sp.* 3.1591, *Caulolatilus
affinis* 2.66, *Eucinostomus dowii* 3.69, *Holacanthus passer* 2.618,
*Stereolepis gigas* 3.08, *Triphoturus mexicanus* 2.79. Cinco salieron del
re-mapeo —estaban ya extraídas y el paso 2 las tiró— y sólo dos del barrido
completo del corpus.

**Cero valores de `a` en 1 122 especies.** No es un fallo de la extracción esta
vez: los papers del corpus reportan la relación de forma cualitativa
(«crecimiento alométrico positivo»), publican la `b` de vez en cuando y la `a`
prácticamente nunca. Esa asimetría es real en la literatura pesquera regional.

La consecuencia para el modelo es directa: **`li_a` sólo puede venir de
FishBase**. La pregunta ya no es «¿lo dice el corpus?» sino si se acepta la
relación longitud–peso curada de FishBase, que es una decisión de la página de
FishBase, no de la cola.

> **La «a» sin unidades no sirve.** `a` depende de si W va en g o kg y L en cm o
> mm: el mismo pez tiene una `a` mil veces distinta según eso. Cuando el paper
> no las declara, la sugerencia lo dice en su justificación y hay que
> resolverlo antes de aceptar.

**Cuando el corpus y FishBase proponen el mismo parámetro, manda el corpus.**
FishBase da la mediana mundial de `poplw`; la cita es de un paper del Golfo, que
es el sistema que se está modelando. Ninguna de las dos se escribe hasta que
alguien acepta — lo que cambia es cuál se muestra pendiente.

## NotebookLM: el canal cuyo corpus no está en el repositorio

Hay literatura —informes técnicos, literatura gris, capítulos nunca digitalizados
como PDF del corpus— que el índice FAISS no tiene y que sí está cargada en dos
notebooks de NotebookLM. Este canal la pone frente al revisor.

### Lo que se investigó antes de escribirlo

A septiembre de 2026 **NotebookLM no tiene API pública**:

| Vía | ¿Permite preguntar a *tus* notebooks? |
|---|---|
| NotebookLM consumidor, API oficial | **No existe.** Google la anuncia «en camino», sin beta ni fecha |
| Gemini Notebook Enterprise, API oficial | Sólo CRUD de notebooks y audio: **no hay endpoint de consulta**. Además exige Google Cloud con licencia |
| Discovery Engine `answer` (Vertex AI Search) | Sí, con citas — pero sobre un Data Store, no sobre el notebook: obliga a resubir los documentos |
| `notebooklm-py` (no oficial) | **Sí.** Es la única vía desde una cuenta personal |

Se eligió la última, con los ojos abiertos: habla APIs internas de Google usando
las cookies de tu sesión y puede dejar de funcionar sin aviso. Toda esa
fragilidad está encerrada en `nblm_client.py`; si Google cambia sus endpoints,
se arregla un archivo.

### La deuda que este canal tiene y los demás no

Una respuesta de NotebookLM **no es reproducible desde este repositorio**. El
corpus del notebook no está versionado aquí, así que nadie puede volver a
ejecutar la consulta y obtener lo mismo. Eso lo distingue de todos los demás
canales, y se maneja con tres decisiones:

1. **El crudo se guarda siempre.** `outputs/review/nblm_extractions.jsonl`
   conserva la respuesta íntegra, las citas y el parseo de cada consulta. Ése,
   y no la conexión, es el activo que perdura: si la librería se rompe mañana,
   el JSONL sigue siendo evidencia auditable.
2. **Un valor sin cita textual se descarta.** Y si la cita no se puede resolver
   a un documento concreto, el valor se emite pero baja de confianza y la
   tarjeta lo dice: «sin fuente identificada» es una afirmación del asistente,
   no un dato de la literatura.
3. **El export lo deja por escrito.** El estado propio es
   `revisado_notebooklm`, y la nota lleva el alcance, los documentos citados y
   —si aplica— que los notebooks discrepaban.

### Por qué dos notebooks, y qué se gana

No se concatenan: se pregunta a cada uno por separado y se reconcilian. La
concordancia entre dos corpus independientes es la señal de confianza más barata
que existe, y la discrepancia es información que un promedio habría escondido.

| Situación | Confianza | Severidad en la cola |
|---|---|---|
| Ambos responden y coinciden (≤ `--tolerancia`, def. 15 %) | alta | `warning` |
| Sólo uno responde | media | `serious` |
| Responden y discrepan | **baja** | `critical` |
| Ninguno responde | — | descarte, con su motivo |

Como el tablero ordena por severidad, **las discrepancias suben solas al
principio de la cola**. La tarjeta muestra siempre los dos valores con su frase
y su documento: lo que el revisor decide no es un número, es cuál de las dos
fuentes aplica al Golfo de California.

### Dos pasos por especie

1. **Pregunta en prosa a NotebookLM**, una por (especie, notebook), pidiendo de
   golpe todos los parámetros que ese notebook declara cubrir en
   `config/notebooklm.json`. NotebookLM aterriza mejor en prosa que forzado a
   JSON, y agrupar por especie en vez de por celda reduce el gasto de cuota unas
   cinco veces.
2. **Parseo de esa prosa a JSON con Claude**, con un system prompt que prohíbe
   aportar conocimiento propio y exige la frase literal. Es el mismo patrón de
   dos pasos que usa `lw_extract.py`.

`params_covered` no es decorativo: preguntarle a un notebook por un parámetro
que no cubre gasta cuota y produce respuestas educadas sin respaldo.

### Puesta en marcha

```bash
pip install "notebooklm-py[browser]"
notebooklm login

cp config/notebooklm.example.json config/notebooklm.json
python3 scripts/phase_7_review/nblm_client.py --listar   # ids -> config

# Prueba de un tiro, sin escribir nada: imprime pregunta, respuesta y parseo
python3 scripts/phase_7_review/nblm_extract.py --dry-run --limit 1

python3 scripts/phase_7_review/nblm_extract.py --limit 10 --group "Peces demersales"
python3 scripts/phase_7_review/nblm_extract.py
python3 scripts/phase_7_review/nblm_extract.py --informe
```

La corrida es **reanudable**: el JSONL guarda una línea por (especie, notebook),
así que una interrupción no obliga a regastar. Y respeta la invariante de todos
los canales automáticos: **una celda que un humano ya aceptó o rechazó no se
vuelve a proponer**.

### Si NotebookLM resultara valioso y estable

El paso siguiente natural sería **exportar los documentos de los dos notebooks e
indexarlos en el índice FAISS/BM25 existente**. Eso elimina la dependencia de la
API no oficial y devuelve la reproducibilidad, a cambio del trabajo de ingesta.
El JSONL crudo de este canal es justo lo que hace falta para decidir si vale la
pena.

## La página de «Todos los parámetros»

Las otras vistas miran una celda a la vez: son para **decidir**. Esta es para
**ver** — `#m`, o «Todos los parámetros →» en la portada.

Una fila por especie, una columna por cada uno de los 16 parámetros, y el
estado de procedencia en el color de fondo. Responde de un vistazo la pregunta
que el modelador se hace antes de alimentar Atlantis: *¿de dónde salió cada
número, y cuánto falta?*

| Color | Estado |
|---|---|
| Verde | `acuerdo` — dos o más búsquedas coinciden |
| Azul | `revisado*` — alguien lo decidió, con la fuente que sea |
| Ámbar | `sin_corroborar` — una sola búsqueda |
| Naranja | `conflicto_pendiente` — discrepan, consenso provisional |
| Rojo | `sin_respaldo_b6` — otras lo afirman, B6 no lo halló |
| Gris, cursiva, entre paréntesis | Propuesta sin aceptar: **no está en el CSV** |

La tabla se calcula con la **misma `consolidate()`** que escribe el CSV, no con
una lectura paralela: lo que se ve es lo que se exportaría al pulsar «Exportar
CSV» ahora mismo. No puede desincronizarse porque no es un resumen aparte.

Las propuestas en gris se apagan con una casilla. Encendidas miden la cobertura
que el modelo ganaría si alguien revisara la cola: hoy **510 celdas con dato
frente a 3 440 propuestas pendientes**, casi todas de FishBase. Apagadas se ve
lo que el dataset tiene de verdad.

Grupo y especie quedan fijos al desplazarse —a la mitad del scroll, si no, ya no
se sabe de qué especie es el número que se mira— y el grupo es un enlace a su
cola de revisión. El tooltip de cada celda lleva el estado, qué búsquedas la
aportaron, el revisor y la nota de procedencia.

## La página de FishBase

FishBase vive fuera de la cola de revisión, en `#fb`. No es una separación
cosmética: la cola sirve para **dirimir celda a celda** —qué búsqueda tiene
razón, si el corpus lo respalda—, y con FishBase esa pregunta no aplica. Son
2 771 valores curados y coherentes entre sí; meterlos en la cola la multiplicaba
por tres y obligaba a revisarlos de uno en uno, que es la peor forma posible de
mirarlos.

La página los presenta como lo que son: **una tabla por grupo, una fila por
especie y una columna por parámetro**. Así se ve de un vistazo si una especie
está completa, si un valor desentona con sus vecinos, o si un grupo entero
merece aceptarse de golpe.

| Nivel | Cómo se acepta |
|---|---|
| Grupo completo | Botón «Aceptar el grupo (N)», con confirmación |
| Una especie | Botón al final de su fila |
| Una celda | ✓ / ✕ al pasar el cursor por encima |

Cada celda muestra el valor y, en superíndice, cuántos registros lo sostienen;
el `title` lleva el rango observado, la confianza y la referencia primaria.
Verde es aceptada, tachada es descartada.

### Lo que la aceptación por lote nunca hace

**No pisa una decisión tomada en la cola de revisión.** Si una celda ya se
resolvió allí con otra fuente —B1, B5, RAG, una referencia externa— aparece
bloqueada (🔒), muestra el valor que se decidió **allí** y no el de FishBase, y
no ofrece botones. La aceptación por grupo la salta y te dice cuántas saltó.

Deshacer desde un botón de lote una decisión que alguien tomó mirando la
evidencia es exactamente lo que no debe poder pasar: al escribir esto había ya
cinco celdas así, de Ricardo y CRNT.

## Archivos

| Ruta | Qué es |
|---|---|
| `build_review_queue.py` | Construye la cola comparando los CSV y fusionando los dos canales de sugerencia |
| `ai_suggestions.py` | Sugerencias taxonómicas de IsMigratory, con cita verificable |
| `ai_autovalidate.py` | Aprueba las sugerencias de IA cuya cita es de la región |
| `fishbase_suggestions.py` | Descarga el snapshot de FishBase y emite sugerencias numéricas |
| `fb_region.py` | Clasifica una procedencia —localidad o cita— en Golfo / Pacífico mexicano / Pacífico oriental |
| `fb_autovalidate.py` | Aprueba las celdas de FishBase medidas en la región |
| `reclassify_vb.py` | Reparte Von_bertalanffy_a/b al esquema nuevo, para revisión |
| `lw_extract.py` | Recupera li_a/li_b del corpus, con cita textual y tres guardas |
| `nblm_client.py` | Fachada sobre `notebooklm-py`: toda la fragilidad de la API no oficial vive aquí |
| `nblm_extract.py` | Pregunta a los dos notebooks y reconcilia sus respuestas en sugerencias |
| `config/notebooklm.json` | Ids y alcance de cada notebook (local, fuera de git; plantilla en `.example.json`) |
| `review_server.py` | API FastAPI + servidor estático |
| `static/` | Interfaz (HTML/CSS/JS sin dependencias) |
| `outputs/review/review_queue.json` | La cola (regenerable) |
| `outputs/review/decisions.json` | Decisiones del revisor, con historial |
| `outputs/review/rag_evidence.json` | Caché de consultas RAG por celda |
| `outputs/review/ai_suggestions.json` | Sugerencias taxonómicas (regenerable) |
| `outputs/review/fishbase_suggestions.json` | Sugerencias de FishBase (regenerable) |
| `outputs/review/reclass_suggestions.json` | Reparto de esquema (regenerable) |
| `outputs/review/lw_suggestions.json` | Peso-talla extraído del corpus (regenerable) |
| `outputs/review/lw_extractions.jsonl` | Crudo de cada consulta de peso-talla, con o sin hallazgo |
| `outputs/review/nblm_suggestions.json` | Sugerencias de NotebookLM, reconciliadas (regenerable) |
| `outputs/review/nblm_extractions.jsonl` | Crudo de cada consulta a NotebookLM: respuesta íntegra, citas y parseo |
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
| `revisado_fishbase` | aceptado en la página de FishBase |
| `validado_region` | **medido en la región**: el registro de FishBase trae localidad del Golfo, el Pacífico mexicano o el Pacífico oriental, y el valor se calculó sólo con esos registros |
| `validado_region_cita` | **inferencia con respaldo regional**: sugerencia de IA cuya cita es literatura del Golfo o del Pacífico mexicano. El valor no está medido |
| `fishbase_pendiente` / `fishbase_rechazado` | propuesto y sin aceptar; **la celda queda vacía** |
| `revisado_reclasificacion` | el revisor confirmó el reparto de columna |
| `revisado_peso_talla` | el revisor confirmó un li_a/li_b extraído del corpus |
| `*_pendiente` | hay una sugerencia sin revisar; **la celda queda vacía a propósito** |

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
