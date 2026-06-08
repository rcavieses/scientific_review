# Descargador Automático de Artículos - ScienceDirect API

Script para descargar en lote artículos científicos del **Golfo de California** y **Pacífico Mexicano** usando la API de ScienceDirect.

## ✨ Características

- ✅ Descarga automática en lote (batch download)
- ✅ Reintentos automáticos en caso de fallos
- ✅ Manejo inteligente de errores y muros de pago
- ✅ Registro de artículos no descargados
- ✅ Sin costo adicional para instituciones con suscripción
- ✅ Verificación de integridad de PDFs
- ✅ Resumen detallado de resultados

## 📋 Requisitos

### Software
- Python 3.7+
- pip (gestor de paquetes Python)

### Instalación de dependencias

```bash
pip install requests
```

### Acceso ScienceDirect
- **Opción 1:** Institución con suscripción a ScienceDirect
  - La institución debe tener acceso a la API
  - El usuario debe estar en la red de la institución o VPN
  - Se proporciona un API key

- **Opción 2:** Cuenta personal con API
  - Registrarse en https://dev.elsevier.com/
  - Solicitar API key
  - Verificar que tu institución/cuenta tenga acceso

## 🚀 Instalación y Configuración

### 1. Obtener el API Key

**Para instituciones:**
1. Contactar al departamento de IT/Biblioteca
2. Solicitar API key para ScienceDirect
3. Verificar que la IP esté autorizada

**Para usuarios individuales:**
1. Ir a https://dev.elsevier.com/
2. Crear cuenta
3. Solicitar API key
4. Verificar suscripción a ScienceDirect

### 2. Configurar el script

```bash
# Opción A: Editar config.json directamente
nano config.json
# Reemplazar "TU_API_KEY_AQUI" con tu API key real
```

O

```bash
# Opción B: Usar el archivo de ejemplo
cp config.example.json config.json
nano config.json
```

**Formato del config.json:**
```json
{
  "api_key": "TU_API_KEY_AQUI",
  "output_dir": "downloaded_pdfs",
  "sleep_between_requests": 1.0,
  "timeout": 30,
  "max_retries": 3,
  "retry_delay": 5
}
```

### 3. Archivo de artículos

El archivo `articles_to_download.csv` contiene:
- 3,297 artículos del Golfo de California
- 2,726 con DOI
- 3,297 con URLs
- Metadatos: especie, título, autores, año, journal, etc.

**Puedes agregar más artículos:**
```bash
# Editar articles_to_download.csv y agregar filas
# Campos requeridos: species, title, doi, url, source
```

## 📥 Uso del Script

### Uso básico

```bash
python3 download_sciencedirect_api.py
```

Esto usará:
- Configuración: `config.json`
- Artículos: `articles_to_download.csv`
- Salida: `downloaded_pdfs/`

### Opciones avanzadas

```bash
# Usar configuración personalizada
python3 download_sciencedirect_api.py --config mi_config.json

# Usar lista de artículos diferente
python3 download_sciencedirect_api.py --articles mis_articulos.csv

# Especificar directorio de salida
python3 download_sciencedirect_api.py --output mis_pdfs/

# Combinado
python3 download_sciencedirect_api.py \
  --config config.json \
  --articles articles_to_download.csv \
  --output pdfs_golfo_california/
```

## 📊 Resultados

Después de ejecutar el script, encontrarás:

```
downloaded_pdfs/
├── descarga_resumen.json          # Resumen en JSON
├── articulos_fallidos.csv         # Artículos no descargados
├── especie_1_DOI.pdf              # PDFs descargados
├── especie_2_DOI.pdf
└── ...
```

### Archivos generados

1. **descarga_resumen.json**
   ```json
   {
     "fecha": "2026-06-06T...",
     "total_articulos": 3297,
     "descargados": 2841,
     "fallidos": 456,
     "saltados": 0,
     "porcentaje_exito": "86.2%",
     "duracion_minutos": "45m"
   }
   ```

2. **articulos_fallidos.csv**
   - Artículos que no se pudieron descargar
   - Motivos: acceso denegado, no disponible, error HTTP, etc.
   - Útil para investigación manual

## ⚙️ Configuración Detallada

### Parámetros en config.json

| Parámetro | Defecto | Descripción |
|-----------|---------|-------------|
| `api_key` | - | API key de ScienceDirect (REQUERIDO) |
| `output_dir` | `downloaded_pdfs` | Carpeta donde guardar PDFs |
| `sleep_between_requests` | 1.0 | Segundos entre peticiones (respetar límites) |
| `timeout` | 30 | Tiempo máximo de espera por descarga (segundos) |
| `max_retries` | 3 | Número de reintentos en caso de fallo |
| `retry_delay` | 5 | Segundos entre reintentos |

### Recomendaciones de configuración

**Para velocidad máxima (respetar límites de API):**
```json
{
  "sleep_between_requests": 0.5,
  "max_retries": 2,
  "retry_delay": 3,
  "timeout": 20
}
```

**Para confiabilidad máxima:**
```json
{
  "sleep_between_requests": 2.0,
  "max_retries": 5,
  "retry_delay": 10,
  "timeout": 60
}
```

## 🔍 Monitoreo de Progreso

El script muestra en tiempo real:
```
[1/3297] Descargando: Zalophus californianus (Scopus)
  ✓ Éxito (DOI): zalophus_californianus_10.1371_journal.pone.0001234.pdf

...

Progreso: 25/3297 | ✓ 23 | ✗ 2 | ETA: 43m
```

## ⚠️ Solución de Problemas

### Error: "API key no configurada"
- Editar `config.json`
- Agregar tu API key válida
- Verificar que no hay espacios extra

### Error: "Acceso denegado (403)"
- Verificar que el API key sea válido
- Verificar que la IP esté autorizada por ScienceDirect
- Si está en VPN, conectar a la VPN de la institución
- Contactar al administrador de biblioteca

### Error: "Timeout"
- Aumentar `timeout` en config.json
- Verificar conexión a internet
- Reducir `sleep_between_requests` puede ayudar

### Algunos artículos no se descargan
- Verificar `articulos_fallidos.csv`
- Algunos artículos pueden estar en preprint o en acceso abierto en otros lugares
- Intentar descargar manualmente desde la URL

## 💡 Casos de Uso

### Investigación Académica
```bash
# Descargar todos los artículos para una tesis
python3 download_sciencedirect_api.py --articles tesis_articulos.csv
```

### Análisis de Literatura
```bash
# Descargar artículos para un meta-análisis
python3 download_sciencedirect_api.py --output analisis_2024/
```

### Biblioteca Digital
```bash
# Crear repositorio local de artículos del Golfo de California
python3 download_sciencedirect_api.py \
  --output biblioteca_goc/ \
  --config config_biblioteca.json
```

## 📝 Licencia y Términos

- ⚖️ Los PDFs descargados están sujetos a los términos de ScienceDirect
- 📜 Para uso académico/educativo dentro de la institución
- 🔒 No compartir archivos descargados fuera de la institución
- 📚 Respetar copyright y derechos de autor

## 🤝 Contribuciones

Para agregar más artículos:
1. Editar `articles_to_download.csv`
2. Agregar filas con DOI y URLs válidos
3. Ejecutar el script

Ejemplo:
```csv
species,source,title,authors,year,journal,doi,url,pubmed_id
Tursiops truncatus,Scopus,Nueva investigación,Smith et al.,2024,Marine Biology,10.1007/xxxxx,https://...,12345
```

## 📞 Soporte

### Para problemas de API key
- Contactar a: https://dev.elsevier.com/support/
- O a tu administrador de biblioteca institucional

### Para problemas del script
- Verificar que Python 3.7+ esté instalado
- Verificar que `requests` esté instalado: `pip list | grep requests`
- Ejecutar con `python3` en lugar de `python`

## 📚 Referencias

- ScienceDirect API Docs: https://dev.elsevier.com/
- Formato CSV: https://tools.ietf.org/html/rfc4180
- DOI System: https://www.doi.org/

---

**Última actualización:** 2026-06-06  
**Versión:** 1.0  
**Compatible con:** Python 3.7+
