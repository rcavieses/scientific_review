# Auditoría de Fuentes de Artículos - Búsqueda y Descarga

Documento técnico que detalla las fuentes de artículos científicos implementadas en el pipeline, y qué editoriales/bases de datos faltan para maximizar la cobertura.

**Fecha de auditoría:** Junio 2026

---

## ÍNDICE

1. [Fuentes implementadas](#fuentes-implementadas)
2. [Estrategias de descarga](#estrategias-de-descarga)
3. [Editoriales faltantes](#editoriales-faltantes)
4. [Plan de implementación](#plan-de-implementación)

---

## FUENTES IMPLEMENTADAS

### En pipeline batch (scripts/phase_2_search/)

#### 1. **PubMed** ✓
- **URL:** https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
- **Cobertura:** 35M+ artículos biomédicos y de life sciences
- **Relevancia para GOC:** Alta (biología marina, oceanografía)
- **Acceso:** Gratuito, sin límites
- **Función:** `search_pubmed()` en search_articles.py
- **Parámetros:** Query PubMed/MeSH, filtro por región_terms

#### 2. **CrossRef** ✓
- **URL:** https://api.crossref.org/
- **Cobertura:** 150M+ metadatos de artículos con DOI
- **Relevancia:** Alta (cobertura multidisciplinar)
- **Acceso:** Gratuito, sin API key
- **Función:** `search_crossref()` en search_articles.py
- **Características:** 
  - Búsqueda por título/abstract/keywords
  - Filtro por años
  - Rate limit: 50 requests/segundo

#### 3. **Scopus** ✓
- **URL:** https://api.elsevier.com/content/search/scopus
- **Cobertura:** 100M+ documentos, 40,000+ revistas
- **Relevancia:** Alta (indexación completa)
- **Acceso:** Requiere suscripción + API key
- **Función:** `search_scopus()` en search_articles.py
- **Características:**
  - Query TITLE-ABS-KEY
  - Filtro por años
  - Sorteo por relevancia/fecha

#### 4. **ScienceDirect** ✓
- **URL:** https://api.elsevier.com/content/search/sciencedirect
- **Cobertura:** 2,500+ revistas, full-text search
- **Relevancia:** Alta (artículos completos)
- **Acceso:** Requiere suscripción + API key
- **Función:** `search_sciencedirect()` en search_articles.py (nueva función Cambio 5)
- **Características:**
  - Full-text search
  - Acceso a content completo
  - Mismo API key que Scopus

#### 5. **ArXiv** ✓
- **URL:** https://arxiv.org/api/
- **Cobertura:** 2.4M preprints de física, CS, bio, matemáticas
- **Relevancia:** Media (preprints sin revisión de pares)
- **Acceso:** Gratuito
- **Función:** `search_arxiv()` en search_articles.py
- **Características:**
  - Búsqueda por categorías (q-bio para biología)
  - Sorting por fecha
  - Max 1000 resultados por búsqueda

### En librería pero NO integrada en batch

#### 6. **BioRxiv/MedRxiv** ✓ (en código, no usado)
- **Cobertura:** ~1.5M preprints de biología y medicina
- **Relevancia:** Media (preprints, sin revisión de pares)
- **Acceso:** Gratuito
- **Estado:** Implementado en `BioRxivAdapter` (scientific_search/adapters.py)
- **Por qué no se usa:** No integrado en `search_articles_batch()`

#### 7. **PLOS** ✓ (en código, no usado)
- **Cobertura:** Public Library of Science (~400K artículos)
- **Relevancia:** Alta (open access revisados por pares)
- **Acceso:** Gratuito
- **Estado:** Implementado en `PlosAdapter` (scientific_search/adapters.py)
- **Por qué no se usa:** No integrado en `search_articles_batch()`

#### 8. **Local PDF** ✓
- **Función:** Indexación de PDFs locales (LocalPdfAdapter)
- **Uso:** Fase 5 - para RAG

---

## ESTRATEGIAS DE DESCARGA

Implementadas en `scripts/phase_3_download/download_pdfs.py`:

### 1. DOI Resolver + Unpaywall ✓
- Resuelve DOI a URL de acceso abierto
- API Unpaywall: `https://api.unpaywall.org/v2/{doi}`
- Valida magic bytes `%PDF` para rechazar paywalls/HTML

### 2. ArXiv Direct Download ✓
- Descarga PDF directamente de arxiv.org
- URL: `https://arxiv.org/pdf/{arxiv_id}.pdf`

### 3. Direct URL Download ✓
- Descarga desde URL proporcionada en metadatos
- Validación:
  - Content-Type = application/pdf
  - Magic bytes = %PDF (primeros 5 bytes)
  - Rechaza Content-Type text/html (paywalls)

### 4. PubMed Central (PMC) ✓
- Si tiene `pubmed_id`, intenta descarga de PMC
- Fallback a DOI resolver si no disponible

---

## EDITORIALES FALTANTES

### TIER 1: Impacto Alto, Esfuerzo Bajo

#### ❌ Frontiers in Marine Science
**CRÍTICA para biología marina**

- **Editorial:** Frontiers
- **Cobertura:** 100+ revistas open access multidisciplinar
- **Ejemplos:** 
  - Frontiers in Marine Science
  - Frontiers in Ecology and Evolution
  - Frontiers in Environmental Science
- **API:** https://www.frontiersin.org/api/
- **Documentación:** Disponible y clara
- **Esfuerzo:** 2-3 horas
- **Recomendación:** **IMPLEMENTAR INMEDIATAMENTE**

#### ❌ eLife
**Open access multidisciplinar, revisado por pares**

- **Editorial:** eLife Sciences
- **Cobertura:** 50K+ artículos, multidisciplinar
- **API:** https://api.elifesciences.org/
- **Características:** 
  - Búsqueda completa
  - Acceso a metadatos y contenido
- **Esfuerzo:** 2 horas
- **Recomendación:** IMPLEMENTAR

#### ⚠️ BioRxiv/MedRxiv/PLOS
**Ya implementados, requieren integración**

- **Estado:** Código existe, falta conectar a `search_articles_batch()`
- **Esfuerzo:** 30 minutos
- **Recomendación:** **QUICK WIN - Integrar HOY**

---

### TIER 2: Impacto Medio

#### ❌ PeerJ
**Open access multidisciplinar**

- **Cobertura:** Biología, medicina, ciencias
- **API:** https://api.peerj.com/
- **Ejemplos:** PeerJ Life Science, PeerJ Computer Science
- **Esfuerzo:** 2 horas
- **Recomendación:** IMPLEMENTAR

#### ❌ Nature/Nature Ecology & Evolution/Nature Communications
**Altamente citadas, pero sin API oficial de búsqueda**

- **Editorial:** Springer Nature
- **Cobertura:** 5,000+ revistas, multidisciplinar
- **API:** 
  - Búsqueda: ❌ No oficial
  - Acceso: Via CrossRef DOI (parcialmente)
- **Alternativa:** 
  - Mejora de búsqueda en CrossRef (buscar "Nature" en publisher field)
  - Web scraping (complejo, violaría ToS)
- **Esfuerzo:** 4-6 horas (investigación + implementación)
- **Recomendación:** EVALUAR después de Priority 1

---

### TIER 3: Impacto Especializado (Biología Marina)

#### ❌ Marine Ecology Progress Series (MEPS)
- **Cobertura:** ~6,000 artículos sobre ecología marina
- **Problema:** Elsevier, sin API de búsqueda pública
- **Alternativa:** Via Scopus/ScienceDirect si hay suscripción

#### ❌ Fisheries Research
- **Cobertura:** ~3,500 artículos sobre pesca/acuicultura
- **Problema:** Elsevier
- **Alternativa:** Via Scopus/ScienceDirect

#### ❌ Journal of Marine Systems
- **Cobertura:** Sistemas marinos
- **Problema:** Elsevier
- **Alternativa:** Via Scopus/ScienceDirect

#### ❌ Deep Sea Research Parts I & II
- **Cobertura:** Oceanografía de aguas profundas
- **Problema:** Elsevier
- **Alternativa:** Via Scopus/ScienceDirect

#### ❌ Coral Reefs
- **Cobertura:** ~2,000 artículos sobre arrecifes
- **Editor:** Springer
- **Problema:** Sin API de búsqueda pública
- **Alternativa:** Via CrossRef DOI o búsqueda directa

**Total faltante especializado:** 15,000+ artículos

---

### TIER 4: Impacto Bajo/Muy Especializado

- **Science (AAAS)** - Sin API, via CrossRef DOI
- **Cell Press** - Sin API, via Scopus/ScienceDirect
- **PNAS** - Sin API, via CrossRef DOI
- **Springer Ecology** - Sin API pública
- **CICESE (institucional MX)** - OAI-PMH disponible
- **CONABIO** - Repositorio sin API oficial
- **Google Scholar** - ❌ Requiere scraping (viola ToS)

---

## ANÁLISIS COMPARATIVO

### Cobertura ACTUAL (implementado)

| Fuente | Artículos | Relevancia GOC | Acceso |
|--------|-----------|-----------------|--------|
| PubMed | 35M+ | Alta | Gratuito |
| CrossRef | 150M+ | Alta | Gratuito |
| Scopus | 100M+ | Alta | Pago |
| ScienceDirect | Millones | Alta | Pago |
| ArXiv | 2.4M | Media | Gratuito |
| **TOTAL** | **~280M+** | - | - |

### Cobertura FALTANTE (Priority 1+2)

| Fuente | Artículos | Relevancia GOC | Esfuerzo |
|--------|-----------|-----------------|----------|
| Frontiers | ~500K | Crítica | Bajo |
| eLife | ~50K | Alta | Bajo |
| BioRxiv/MedRxiv | 1.5M | Media | Mínimo |
| PLOS | 400K | Alta | Mínimo |
| PeerJ | ~100K | Media | Bajo |
| **TOTAL** | **~2.5M+** | - | - |

### Cobertura ESPECIALIZADA (Priority 3)

- Revistas marinas: ~15,000 artículos
- Requiere suscripción o scraping (Elsevier/Springer)

---

## PLAN DE IMPLEMENTACIÓN

### Fase 1: QUICK WINS (30 min - 1 hora)

```python
# En search_articles_batch(), añadir:
all_results.extend(search_biorxiv(species_name, region_terms=region_terms))
all_results.extend(search_plos(species_name, region_terms=region_terms))
```

**Beneficio:** +1.9M artículos

---

### Fase 2: Priority 1 (2-3 horas c/u)

#### 2a. Implementar FrontiersAdapter

```python
# nuevo archivo: scientific_search/adapters.py
class FrontiersAdapter(BaseAdapter):
    BASE_URL = "https://www.frontiersin.org/api/search"
    
    def search(self, query, max_results=10, year_start=None, year_end=None):
        # Implementar búsqueda Frontiers
        # Registrar en AVAILABLE_ADAPTERS
        # Integrar en search_articles_batch()
```

**Beneficio:** +500K artículos, especializados en biología marina

#### 2b. Implementar eLifeAdapter

```python
# nuevo archivo: scientific_search/adapters.py
class eLifeAdapter(BaseAdapter):
    BASE_URL = "https://api.elifesciences.org/search"
    
    def search(self, query, max_results=10, year_start=None, year_end=None):
        # Implementar búsqueda eLife
        # Registrar en AVAILABLE_ADAPTERS
        # Integrar en search_articles_batch()
```

**Beneficio:** +50K artículos open access revisados

---

### Fase 3: Priority 2 (4-6 horas)

#### 3a. Implementar PeerJAdapter
- Similar a eLife
- **Beneficio:** +100K artículos

#### 3b. Mejorar búsqueda de Nature/Springer
- Investigar opciones:
  - CrossRef DOI con filtro por publisher
  - Web scraping responsable (rate limiting)
  - Contactar Springer para API de acceso

---

### Fase 4: Optional (8+ horas)

- Scraping de revistas marinas especializadas
- Integración OAI-PMH para repositorios institucionales
- Conectores para CICESE/CONABIO

---

## IMPACTO ESPERADO

| Fase | Nuevos artículos | Implementación | ROI |
|------|------------------|-----------------|-----|
| **Actual** | 280M+ | ✓ | - |
| **+ Quick Wins** | +1.9M | 30 min | 🟢 Alto |
| **+ Priority 1** | +550K | 4-6 h | 🟢 Alto |
| **+ Priority 2** | +100K | 4-6 h | 🟡 Medio |
| **+ Priority 3** | +15K | 8+ h | 🔴 Bajo |
| **TOTAL** | ~282.5M+ | 16-20 h | ✓ |

---

## CONCLUSIONES

1. **Cobertura actual es sólida** (280M+ artículos via PubMed, CrossRef, Scopus, ScienceDirect)

2. **Quick wins inmediatos:**
   - Integrar BioRxiv/PLOS (ya en código)
   - Implementar Frontiers (crítico para biología marina)

3. **Falta de APIs oficiales** es el mayor bloqueador para Nature, Science, Cell Press, revistas marinas especializadas

4. **Estrategia recomendada:**
   - Fase 1: Integrar BioRxiv/PLOS (30 min)
   - Fase 2: Implementar Frontiers + eLife (4-6 h)
   - Fase 3: Investigar opciones para Nature/Springer
   - Fase 4: Opcional - revistas marinas especializadas

---

**Documento actualizado:** Junio 2026
**Responsable:** Consolidación del pipeline
