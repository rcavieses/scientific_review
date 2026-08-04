# 🔧 Configuración del Ambiente - Scientific Review

## ✅ Estado Actual
El ambiente se ha configurado exitosamente con todas las dependencias instaladas.

**Python Version**: 3.10.12  
**Virtual Environment**: `venv/`  
**Dependencias Instaladas**: ✓ Todas las del requirements.txt

## 🚀 Activar el Ambiente

### Opción 1: Script Rápido (Recomendado)
```bash
source activate.sh
```

### Opción 2: Manual
```bash
source venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
```

## 📋 Dependencias Instaladas

### Core Libraries
- ✅ **anthropic** (0.101.0) - Cliente API de Anthropic
- ✅ **ollama** (0.6.2) - Soporte para LLMs locales
- ✅ **numpy** (2.2.6) - Computación numérica
- ✅ **pandas** (2.3.3) - Análisis de datos

### ML & Embeddings
- ✅ **sentence-transformers** (5.5.0) - Generación de embeddings
- ✅ **torch** (2.11.0) - Framework de aprendizaje profundo
- ✅ **faiss-cpu** (1.13.2) - Búsqueda vectorial eficiente
- ✅ **scikit-learn** (1.7.2) - ML tradicional
- ✅ **scipy** (1.15.3) - Computación científica

### NLP & PDF Processing
- ✅ **spacy** (3.8.14) - Procesamiento NLP (con modelo `en_core_web_sm`)
- ✅ **pdfplumber** (0.11.9) - Extracción de texto de PDFs
- ✅ **PyPDF2** (3.0.1) - Manipulación de PDFs

### Utilidades
- ✅ **networkx** (3.4.2) - Análisis de grafos
- ✅ **tqdm** (4.67.3) - Barras de progreso
- ✅ **python-dotenv** (1.2.2) - Gestión de variables de entorno
- ✅ **pytest** (9.0.3) - Framework de testing
- ✅ **colorama** (0.4.6) - Colores en terminal

## ⚙️ Configuración Requerida

### 1. API Key de Anthropic
Edita el archivo `.env` y añade tu API key:

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Obtén tu API key en: https://console.anthropic.com/

### 2. Configuración de Ollama (Opcional)
Si deseas usar LLMs locales con Ollama:

```bash
# Instala Ollama desde https://ollama.ai
# Luego ejecuta:
ollama pull llama2

# Actualiza .env si es necesario:
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

### 3. Variables de Entorno
Ya están preconfiguradas en `.env`:
- `RAG_INDEX_DIR` - Directorio para índices FAISS
- `SEARCH_RESULTS_DIR` - Directorio para resultados de búsqueda
- `PDFS_DIR` - Directorio para PDFs descargados

## 📂 Estructura de Directorios

```
scientific_review/
├── venv/                          # Ambiente virtual (creado ✓)
├── outputs/                       # Resultados (creado ✓)
│   ├── search_results/           # Búsquedas en CSV
│   ├── pdfs/                     # PDFs descargados
│   └── rag_index/                # Índices FAISS
├── secrets/                       # Claves de API (creado ✓)
├── logs/                         # Archivos de log (creado ✓)
├── .env                          # Variables de entorno ⚠️ REQUIERE CONFIG
├── .env.example                  # Ejemplo de .env
├── activate.sh                   # Script para activar ambiente
└── requirements.txt              # Dependencias
```

## 🧪 Verificar la Instalación

```bash
# Activar ambiente
source activate.sh

# Verificar importaciones principales
python -c "import anthropic; import sentence_transformers; import spacy; print('✓ Todo OK')"

# Ver lista de paquetes instalados
pip list
```

## 🎯 Próximos Pasos

1. **Configura tu API Key de Anthropic** en `.env`
2. **Activa el ambiente**: `source activate.sh`
3. **Prueba un script**: 
   ```bash
   python consultar_parametros_rag.py --help
   ```

## 📖 Uso del Proyecto

### Buscar especies
```bash
python pipeline_especies.py --especie 1
```

### Descargar PDFs
```bash
python pipeline_especies.py --download --max-results 10
```

### Crear índice RAG
```bash
python pipeline_especies.py --download --index
```

### Consultar con RAG
```bash
python consultar_parametros_rag.py "población de sardinas"
```

## ❓ Troubleshooting

### Error: "No module named 'anthropic'"
```bash
# Asegúrate de que el ambiente está activado
source activate.sh

# Reinstala si es necesario
pip install anthropic
```

### Error: "ANTHROPIC_API_KEY not found"
```bash
# Configura en .env
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
source activate.sh
```

### Error: spacy model not found
```bash
# Descarga el modelo
python -m spacy download en_core_web_sm
```

## 📞 Soporte

Para más información sobre el proyecto, ver:
- `README_PIPELINE_ESPECIES.md` - Uso del pipeline
- `requirements.txt` - Dependencias
- Código fuente en carpeta raíz

---
**Ambiente configurado el**: 2026-05-12  
**Última actualización**: Setup completado ✓
