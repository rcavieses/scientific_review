# Índice de Archivos - ScienceDirect Batch Downloader

## 📂 Estructura

```
sciencedirect_batch_downloader/
│
├── 📄 Scripts Principales
│   ├── download_sciencedirect_api.py    ← Script de descarga (PRINCIPAL)
│   ├── test_api.py                      ← Validador de configuración
│   ├── run.sh                           ← Ejecutable para Linux/Mac
│   └── run.bat                          ← Ejecutable para Windows
│
├── 📋 Configuración
│   ├── config.json                      ← Tu configuración (EDITAR ESTO)
│   └── config.example.json              ← Ejemplo de configuración
│
├── 📊 Datos
│   └── articles_to_download.csv         ← 3,297 artículos a descargar
│
├── 📚 Documentación
│   ├── README.md                        ← Documentación completa
│   ├── QUICKSTART.md                    ← Guía rápida (5 minutos)
│   └── INDEX.md                         ← Este archivo
│
└── 📁 downloaded_pdfs/ (se crea automáticamente)
    ├── descarga_resumen.json
    ├── articulos_fallidos.csv
    └── [3,000+ PDFs descargados]
```

## 🚀 Inicio Rápido

### Opción A: Script Interactivo (Recomendado)

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

**Windows:**
```cmd
run.bat
```

### Opción B: Manual

```bash
# 1. Validar
python3 test_api.py

# 2. Descargar
python3 download_sciencedirect_api.py

# 3. Revisar resultados
ls -lah downloaded_pdfs/
```

## 📄 Descripción de Archivos

### Scripts Ejecutables

#### `download_sciencedirect_api.py` ⭐ PRINCIPAL
- **Propósito:** Descargar artículos en lote
- **Entrada:** `articles_to_download.csv`
- **Salida:** `downloaded_pdfs/`
- **Uso:** `python3 download_sciencedirect_api.py`

**Características:**
- ✓ Descarga automática en lote (batch)
- ✓ Reintentos automáticos
- ✓ Manejo de errores y muros de pago
- ✓ Registro de artículos fallidos
- ✓ Resumen detallado

#### `test_api.py`
- **Propósito:** Validar configuración antes de descargar
- **Entrada:** `config.json`
- **Salida:** Reporte de validación
- **Uso:** `python3 test_api.py`

**Comprueba:**
- ✓ Configuración JSON válida
- ✓ API key correcto
- ✓ Archivo de artículos válido

#### `run.sh` (Linux/Mac)
- **Propósito:** Ejecutable con interfaz interactiva
- **Uso:** `./run.sh`
- **Automático:** Verifica Python, dependencias, configura, valida y descarga

#### `run.bat` (Windows)
- **Propósito:** Ejecutable con interfaz interactiva para Windows
- **Uso:** Doble clic o `run.bat`
- **Automático:** Igual que `run.sh` pero para Windows

### Archivos de Configuración

#### `config.json` 🔐 EDITAR ESTO
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

**Campos:**
- `api_key`: Tu API key de ScienceDirect (REQUERIDO)
- `output_dir`: Dónde guardar los PDFs
- `sleep_between_requests`: Segundos entre peticiones (respetar límites)
- `timeout`: Tiempo máximo de espera (segundos)
- `max_retries`: Reintentos en caso de fallo
- `retry_delay`: Segundos entre reintentos

#### `config.example.json`
- Ejemplo de configuración
- Usar como plantilla si necesitas reset

### Datos

#### `articles_to_download.csv`
- **Contenido:** 3,297 artículos del Golfo de California
- **Campos:** species, source, title, authors, year, journal, doi, url, pubmed_id
- **Estadísticas:**
  - 3,297 artículos totales
  - 2,726 con DOI
  - 3,297 con URL

**Puedes:**
- Editar para agregar/quitar artículos
- Usar como referencia
- Crear versiones personalizadas (--articles mi_lista.csv)

### Documentación

#### `README.md` 📖 COMPLETO
- Documentación detallada y completa
- Requisitos y instalación
- Configuración avanzada
- Solución de problemas
- Referencias y enlaces útiles

**Secciones:**
- ✓ Características
- ✓ Requisitos
- ✓ Instalación
- ✓ Uso básico y avanzado
- ✓ Configuración detallada
- ✓ Monitoreo de progreso
- ✓ Solución de problemas
- ✓ Casos de uso
- ✓ Licencia y términos

#### `QUICKSTART.md` ⚡ RÁPIDO
- Guía de 5 minutos
- Pasos esenciales
- Solución rápida de problemas
- FAQ

#### `INDEX.md` 📋 ESTE ARCHIVO
- Descripción de estructura
- Guía de navegación
- Resumen de archivos

## 🔧 Tareas Comunes

### Configurar por primera vez
1. Abrir `config.json` con editor de texto
2. Reemplazar `api_key` con tu clave
3. Guardar
4. Ejecutar `python3 test_api.py` para validar

### Descargar artículos
```bash
python3 run.sh        # Linux/Mac interactivo
# o
python3 download_sciencedirect_api.py  # Directo
```

### Monitorear progreso
```bash
tail -f downloaded_pdfs/descarga.log   # Linux/Mac
# o ver la salida del script en tiempo real
```

### Revisar fallidos
```bash
cat downloaded_pdfs/articulos_fallidos.csv
```

### Ver estadísticas
```bash
cat downloaded_pdfs/descarga_resumen.json
```

## 📊 Salida Esperada

Después de ejecutar, encontrarás en `downloaded_pdfs/`:

```
downloaded_pdfs/
├── descarga_resumen.json           ← Estadísticas en JSON
├── articulos_fallidos.csv          ← Artículos no descargados
├── zalophus_californianus_10.1371_journal.pone.0001234.pdf
├── vinciguerria_lucetia_10.1371_journal.pone.0001235.pdf
├── tursiops_truncatus_10.1371_journal.pone.0001236.pdf
├── totoaba_macdonaldi_10.1371_journal.pone.0001237.pdf
└── ... (3000+ más)
```

### Contenido de `descarga_resumen.json`
```json
{
  "fecha": "2026-06-06T23:00:00",
  "total_articulos": 3297,
  "descargados": 2841,
  "fallidos": 456,
  "saltados": 0,
  "porcentaje_exito": "86.2%",
  "duracion_minutos": "45m"
}
```

## 🔐 Seguridad

- ⚠️ **NO** compartir `config.json` (contiene API key)
- ⚠️ **NO** publicar API key en GitHub/internet
- ⚠️ Mantener API key privado
- ⚠️ Los PDFs descargados son solo para uso académico/educativo

## 📞 Soporte

### Si `test_api.py` falla

1. **"API key no configurada"**
   - Editar `config.json`
   - Agregar API key válida

2. **"API key inválido (401)"**
   - Verificar que el API key sea correcto
   - Regenerar en https://dev.elsevier.com/

3. **"Acceso denegado (403)"**
   - Conectar a VPN de institución
   - Verificar IP autorizada
   - Contactar biblioteca institucional

4. **"Timeout"**
   - Aumentar `timeout` en config.json
   - Aumentar `sleep_between_requests`
   - Verificar conexión a internet

### Para ayuda general
- Ver `README.md` sección "Solución de Problemas"
- Ver `QUICKSTART.md` sección "Solución de Problemas Rápida"

## 🎓 Información Institucional

Si tu institución no tiene API key:

1. **Contactar biblioteca** → Solicitar API key de ScienceDirect
2. **Verificar suscripción** → ¿Tiene acceso a ScienceDirect?
3. **Solicitar acceso** → La mayoría de universidades pueden solicitar

**Contactos útiles:**
- ScienceDirect Support: https://dev.elsevier.com/support/
- Biblioteca de tu institución
- Departamento de IT

## 📈 Estadísticas del Proyecto

- **Artículos:** 3,297
- **Especies:** 1,159 únicas
- **Revistas principales:** Ciencias Marinas, Revista de Biología Tropical, etc.
- **Rango temporal:** 1987-2026
- **Región:** Golfo de California y Pacífico Mexicano

## 🚀 Próximos Pasos

1. **Editar `config.json`** con tu API key
2. **Ejecutar `python3 test_api.py`** para validar
3. **Ejecutar descarga:**
   - Linux/Mac: `./run.sh`
   - Windows: `run.bat`
   - Manual: `python3 download_sciencedirect_api.py`
4. **Esperar** 1-2 horas
5. **Revisar** resultados en `downloaded_pdfs/`

---

**Última actualización:** 2026-06-06  
**Versión:** 1.0  
**Autor:** Scientific Review Project  
**Licencia:** Uso académico y educativo
