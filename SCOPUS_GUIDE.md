# Guía: Búsqueda Avanzada con Scopus y ScienceDirect

## 📚 Bases de Datos Disponibles

### Scopus (Recomendado)
- **Cobertura**: >24 millones de artículos
- **Disciplinas**: Todas (ciencias, tecnología, medicina, ingeniería)
- **API**: Elsevier Scopus API
- **Precio**: Requiere suscripción institucional

### ScienceDirect
- **Cobertura**: >18 millones de artículos
- **Disciplinas**: Multidisciplinario
- **API**: Elsevier ScienceDirect API
- **Precio**: Requiere suscripción institucional

### Alternativas Gratuitas
- **PubMed**: 35+ millones de referencias médicas (ya implementado)
- **CrossRef**: 150+ millones de DOIs (ya implementado)
- **ArXiv**: Preprints de física, matemáticas, CS (ya implementado)

---

## 🔑 Obtener API Keys

### Opción 1: Scopus API (Recomendado)

1. **Crear cuenta en Elsevier Developer Portal**
   ```
   https://dev.elsevier.com
   ```

2. **Registrarse/Login**
   - Click en "Sign Up" o "Sign In"
   - Crear cuenta con email institucional

3. **Crear Aplicación**
   - Ir a "My Apps"
   - Click en "Create New App"
   - Rellenar nombre y descripción
   - Aceptar términos

4. **Obtener API Key**
   - Verás la API key en "API Key Management"
   - Copiar el "APIKey"

5. **Configurar en el proyecto**
   ```bash
   cp .env.example .env
   # Editar .env con tu API key:
   # SCOPUS_API_KEY=tu_api_key_aqui
   ```

### Opción 2: ScienceDirect API

El proceso es similar a Scopus (mismo portal de Elsevier):

1. Ir a https://dev.elsevier.com
2. Crear app para ScienceDirect
3. Copiar API key a `.env`:
   ```
   SCIENCEDIRECT_API_KEY=tu_api_key_aqui
   ```

---

## 📋 Requisitos Previos

- **Acceso institucional**: Generalmente las universidades tienen licencia
- **Email institucional**: Recomendado para registro
- **Sin costo**: Si tu institución tiene suscripción

---

## 🚀 Uso

### Búsqueda Individual en Scopus

```bash
# Búsqueda simple
python3 search_scopus.py "Acanthaster planci"

# Con más resultados
python3 search_scopus.py "coral reef" --max 100

# Guardar en CSV
python3 search_scopus.py "Acanthaster planci" -o resultados.csv

# Ver en JSON
python3 search_scopus.py "fish diseases" --json
```

### Búsqueda Individual en ScienceDirect

```bash
# Búsqueda simple
python3 search_sciencedirect.py "Marine biodiversity"

# Con máximo de resultados
python3 search_sciencedirect.py "Coral bleaching" --max 100

# Guardar resultados
python3 search_sciencedirect.py "Ocean acidification" -o resultados.csv
```

---

## 📊 Ejemplo de Salida

```
✅ Encontrados 25 artículos

1. Acanthaster planci (Crown-of-thorns starfish): physiology and ecology
   Autores: Birkeland C, Lucas JS, Vago FJ
   Journal: Chemical Ecology (2022)
   Citaciones: 157
   DOI: 10.1016/j.jembe.2021.151689
   Resumen: A comprehensive review of Crown-of-thorns starfish ecology...

2. Outbreaks of Acanthaster planci: understanding coral reef dynamics
   ...
```

---

## 🔄 Integrar con el Pipeline

### Usar Scopus en búsqueda completa

```bash
# Editar .env con tu API key
echo "SCOPUS_API_KEY=your_key_here" >> .env

# El pipeline automáticamente usará Scopus si la key existe
python3 cli.py trigger-pipeline
```

### Buscar para especie específica

```bash
# Búsqueda individual
python3 search_scopus.py "Acanthaster planci" -o acanthaster_scopus.csv

# Luego procesar descargas
python3 download_pdfs.py --search-results . --output pdfs/
```

---

## 💡 Consejos

### Rate Limits
- **Scopus**: ~2 req/sec
- **ScienceDirect**: Varía según licencia
- Si ves error 429: espera y reintentar

### Mejores Prácticas
- Usar nombres científicos completos: "Acanthaster planci" vs "acanthaster"
- Agregar términos relacionados: "Acanthaster planci outbreak"
- Filtrar por año si es necesario

### Troubleshooting

**"API key inválida"**
```bash
# Verificar que .env tenga la key correcta
cat .env | grep SCOPUS

# O usar variable de entorno
export SCOPUS_API_KEY=tu_key_aqui
python3 search_scopus.py "fish"
```

**"Rate limit excedido"**
```bash
# Esperar unos minutos y reintentar
# O reducir el número de búsquedas simultáneas
```

**"No se encuentran artículos"**
- Verificar ortografía
- Intentar con términos más generales
- Usar comillas para búsqueda exacta: `"Acanthaster planci"`

---

## 📈 Estadísticas Esperadas

Para 3,814 especies MARINE:

| Fuente | Cobertura | Artículos/especie | Total estimado |
|--------|-----------|-------------------|----------------|
| PubMed | ~5% | 0-2 | ~3,000-5,000 |
| CrossRef | ~60% | 5-10 | ~20,000-30,000 |
| ArXiv | ~1% | 0-1 | ~500-1,000 |
| Scopus | ~80%+ | 8-15 | ~30,000-50,000 |
| ScienceDirect | ~60% | 5-10 | ~20,000-30,000 |
| **TOTAL** | - | - | **~75,000-115,000** |

---

## 🆘 Soporte

Para más información:
- Documentación Scopus: https://dev.elsevier.com/sc_apis.html
- Documentación ScienceDirect: https://dev.elsevier.com/sd_apis.html
- Contactar a Elsevier: https://www.elsevier.com/about/contact

