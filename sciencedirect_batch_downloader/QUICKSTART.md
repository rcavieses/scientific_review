# Guía Rápida (5 minutos)

## Para usuarios con acceso institucional a ScienceDirect

### Paso 1: Obtener API Key (2 minutos)

Contacta a tu **biblioteca universitaria** o **departamento de IT**:

> "Necesito un API key de ScienceDirect para descargar artículos en mi investigación"

Te darán algo como:
```
api_key = "1234567890abcdef1234567890abcdef"
```

### Paso 2: Configurar (1 minuto)

Abre `config.json` con tu editor favorito:

```bash
nano config.json
```

Reemplaza:
```json
{
  "api_key": "1234567890abcdef1234567890abcdef",
  "output_dir": "downloaded_pdfs",
  ...
}
```

Guarda con `Ctrl+O` → `Enter` → `Ctrl+X`

### Paso 3: Validar (1 minuto)

```bash
python3 test_api.py
```

Deberías ver:
```
✓ Archivo JSON válido
✓ Campos requeridos presentes
✓ API key válido
✓ 3297 artículos para descargar
  - Con DOI: 2726
  - Con URL: 3297

✓ TODO LISTO - Puedes ejecutar download_sciencedirect_api.py
```

### Paso 4: Descargar (esperar)

```bash
python3 download_sciencedirect_api.py
```

El script descargará automáticamente ~3,297 artículos:

```
[1/3297] Descargando: Zalophus californianus (Scopus)
  ✓ Éxito (DOI): zalophus_californianus_10.1371_journal.pone.0001234.pdf

[2/3297] Descargando: Vinciguerria lucetia (Scopus)
  ✓ Éxito (DOI): vinciguerria_lucetia_10.1371_journal.pone.0001234.pdf

...

Progreso: 25/3297 | ✓ 23 | ✗ 2 | ETA: 43m
```

**Tiempo total: 1-2 horas** (depende del servidor)

### Paso 5: Revisar resultados

```bash
ls -lah downloaded_pdfs/
```

Encontrarás:
- 📄 **2,500+ PDFs** descargados
- 📋 **descarga_resumen.json** - estadísticas
- 📋 **articulos_fallidos.csv** - artículos que no se bajaron

## Solución de Problemas Rápida

| Problema | Solución |
|----------|----------|
| `API key no configurada` | Editar `config.json` y agregar tu API key |
| `Acceso denegado (403)` | Conectar a VPN de la institución |
| `API key inválido (401)` | Verificar que el API key sea correcto |
| `Timeout` | Aumentar `timeout` en config.json a 60 |
| `Red lenta` | Aumentar `sleep_between_requests` a 2.0 |

## Estructura de Carpetas

```
sciencedirect_batch_downloader/
├── download_sciencedirect_api.py    # Script principal
├── test_api.py                      # Script de validación
├── config.json                      # Tu configuración
├── config.example.json              # Ejemplo de configuración
├── articles_to_download.csv         # Artículos a descargar
├── downloaded_pdfs/                 # Salida (se crea automáticamente)
│   ├── descarga_resumen.json
│   ├── articulos_fallidos.csv
│   └── [3297 PDFs...]
└── README.md                        # Documentación completa
```

## Casos de Uso Comunes

### Descargar todos los artículos
```bash
python3 download_sciencedirect_api.py
```

### Descargar solo una especie
```bash
# Crear new_list.csv con solo esa especie
# Luego:
python3 download_sciencedirect_api.py --articles new_list.csv
```

### Descargar a carpeta personalizada
```bash
python3 download_sciencedirect_api.py --output mi_carpeta/
```

### Usar configuración alternativa
```bash
cp config.json config_backup.json
python3 download_sciencedirect_api.py --config config_backup.json
```

## Comandos Útiles

```bash
# Ver progreso en tiempo real
tail -f downloaded_pdfs/descarga.log

# Contar PDFs descargados
ls downloaded_pdfs/*.pdf | wc -l

# Ver resumen
cat downloaded_pdfs/descarga_resumen.json

# Ver artículos que fallaron
cat downloaded_pdfs/articulos_fallidos.csv | head -20

# Estadísticas detalladas
python3 -c "
import json
with open('downloaded_pdfs/descarga_resumen.json') as f:
    data = json.load(f)
    for k, v in data.items():
        print(f'{k}: {v}')
"
```

## FAQ Rápido

**P: ¿Costo?**
A: Sin costo si tu institución tiene suscripción a ScienceDirect

**P: ¿Puedo compartir los PDFs?**
A: Solo dentro de tu institución. Los PDF tienen restricciones de copyright

**P: ¿Cuánto tiempo toma?**
A: 1-2 horas para 3,297 artículos (depende del servidor y tu internet)

**P: ¿Qué hago si algunos no se descargan?**
A: Revisar `articulos_fallidos.csv` e intentar descargar manualmente

**P: ¿Necesito instalar algo más?**
A: Solo Python 3.7+ y `pip install requests`

## Contacto Institucional

Si tu institución no tiene API key de ScienceDirect:

1. **Contactar biblioteca**: "Necesitamos acceso a ScienceDirect API"
2. **Verificar suscripción**: ¿Tiene tu institución suscripción a ScienceDirect?
3. **Solicitar acceso**: La mayoría de instituciones pueden solicitar acceso a la API

---

**¿Necesitas ayuda?** Ver `README.md` para documentación completa
