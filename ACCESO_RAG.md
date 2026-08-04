# 🐟 Acceso al Modelo RAG - Guía para Colegas

Este documento describe las formas en que tus colegas pueden acceder al modelo RAG de búsqueda científica.

## 📊 Características

- **10,500 chunks** indexados de papers científicos
- **429 papers** del Golfo de California
- **Búsqueda semántica** con embeddings
- **Síntesis con Claude API** para respuestas estructuradas
- **Integración FishBase** para parámetros biológicos
- **Citas automáticas** de fuentes

---

## 🌐 Opción 1: Interfaz Web (Recomendado)

**Más accesible para usuarios no técnicos.**

### Paso 1: Iniciar el servidor

```bash
cd /home/atlantis/scientific_review
set -a && source .env && set +a
python3 scripts/phase_6_query/server_rag_api.py --host 0.0.0.0 --port 8000
```

El servidor estará disponible en:
- 🌐 **Web UI:** http://localhost:8000
- 📡 **API REST:** http://localhost:8000/docs
- ✅ **Health:** http://localhost:8000/api/health

### Paso 2: Compartir con colegas

#### Acceso Local (misma red):
```
http://[tu-ip]:8000
```

Encuentra tu IP:
```bash
hostname -I
```

#### Acceso Remoto (internet):
1. Usar ngrok:
```bash
pip install ngrok
python3 -c "from ngrok import ngrok; print(ngrok.connect(8000))"
```

2. O usar SSH tunneling:
```bash
# En tu máquina:
ssh -R 8000:localhost:8000 [colega@servidor-remoto]

# En máquina remota:
http://localhost:8000
```

---

## 🐍 Opción 2: CLI Interactivo

**Para usuarios técnicos que prefieren terminal.**

### Instalación (una sola vez):

```bash
cd /home/atlantis/scientific_review
pip install -r requirements.txt
```

### Uso:

#### Consulta simple:
```bash
set -a && source .env && set +a && \
PYTHONPATH=/home/atlantis/scientific_review python3 \
scripts/phase_6_query/buscar_rag_con_fishbase.py \
  "Tu pregunta aquí" \
  --index-dir outputs/rag_index_goc
```

#### Modo interactivo:
```bash
set -a && source .env && set +a && \
PYTHONPATH=/home/atlantis/scientific_review python3 \
scripts/phase_6_query/buscar_rag_con_fishbase.py \
  --index-dir outputs/rag_index_goc \
  --interactive
```

#### Ver estadísticas:
```bash
set -a && source .env && set +a && \
PYTHONPATH=/home/atlantis/scientific_review python3 \
scripts/phase_6_query/buscar_rag_con_fishbase.py \
  --stats \
  --index-dir outputs/rag_index_goc
```

---

## 🔗 Opción 3: API REST (Programático)

**Para integración con otras aplicaciones.**

### Iniciar servidor:
```bash
cd /home/atlantis/scientific_review
set -a && source .env && set +a
python3 scripts/phase_6_query/server_rag_api.py --port 8000
```

### Endpoints disponibles:

#### GET `/api/stats`
Obtener estadísticas del índice.

```bash
curl http://localhost:8000/api/stats
```

**Respuesta:**
```json
{
  "total_chunks": 10500,
  "total_papers": 429,
  "embedding_model": "all-MiniLM-L6-v2",
  "embedding_dimension": 384,
  "last_updated": "2026-07-30T19:10:39.956013"
}
```

#### POST `/api/query`
Ejecutar una consulta RAG.

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "¿Cuál es la talla máxima del Huachinango?",
    "top_k": 5,
    "min_score": 0.2,
    "include_fishbase": true,
    "include_chunks": false
  }'
```

**Respuesta:**
```json
{
  "question": "¿Cuál es la talla máxima del Huachinango?",
  "answer": "Basándome en los fragmentos...",
  "sources": [
    {
      "paper_id": "Smith2020",
      "authors": ["Smith, J.", "Johnson, A."],
      "year": 2020,
      "score": 0.85,
      "page": 5,
      "text": "El Huachinango..."
    }
  ],
  "chunks_used": 5,
  "model": "claude-haiku-4-5-20251001",
  "execution_time_ms": 2350.5,
  "fishbase_data": "..."
}
```

#### GET `/api/health`
Verificar estado del servidor.

```bash
curl http://localhost:8000/api/health
```

---

## 🚀 Opción 4: Docker (Distribución Completa)

**Fácil para colegas sin configuración previa.**

### Crear Dockerfile:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar proyecto
COPY . .

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Exponer puerto
EXPOSE 8000

# Comando por default
CMD ["python3", "scripts/phase_6_query/server_rag_api.py", "--host", "0.0.0.0", "--port", "8000"]
```

### Construir y ejecutar:

```bash
# Construir imagen
docker build -t scientific-review-rag .

# Ejecutar contenedor
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY="tu-api-key" \
  scientific-review-rag
```

Luego accede a http://localhost:8000

---

## 📚 Opción 5: Jupyter Notebook

**Para análisis interactivo avanzado.**

### Crear notebook:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from pipeline.rag import VectorDBManager
from pipeline.rag.query_engine import RAGQueryEngine
from pipeline.llm import get_llm_provider

# Cargar índice
db = VectorDBManager(
    index_dir=Path("outputs/rag_index_goc"),
    embedding_dim=384
)
db.load()

# Crear motor RAG
llm_provider = get_llm_provider(provider="claude", model="claude-haiku-4-5-20251001")
engine = RAGQueryEngine(vector_db=db, llm_provider=llm_provider)

# Ejecutar consulta
result = engine.query("¿Cuál es la talla máxima del Huachinango?")
print(result.answer)
```

---

## ⚙️ Configuración para Colegas

### Requisitos:
- **Python 3.10+**
- **API Key de Anthropic** (gratis hasta cierto límite)
- **Acceso a internet** (para Claude API)

### Instalación rápida:

```bash
# 1. Clonar/descargar proyecto
git clone [repo-url]
cd scientific_review

# 2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # en Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar API key
echo "ANTHROPIC_API_KEY=tu-api-key" > .env

# 5. Ejecutar servidor
python3 scripts/phase_6_query/server_rag_api.py
```

---

## 🔐 Seguridad y Privacidad

- Los papers científicos quedan indexados localmente
- Las consultas se envían a Claude API (ver política de privacidad de Anthropic)
- No se almacenan preguntas en la base de datos
- Recomendado usar VPN para acceso remoto

---

## 🐛 Solución de Problemas

### Error: "RAG no inicializado"
- Verificar que el índice existe en `outputs/rag_index_goc/`
- Verificar que ANTHROPIC_API_KEY está configurada

### Error de conexión a FishBase
- Es normal, FishBase puede estar no disponible
- El RAG seguirá funcionando con papers científicos

### Servidor lento
- Verificar conexión a internet
- Esperar a que termine de cargar el modelo de embeddings
- Verificar memoria disponible (necesita ~2GB)

---

## 📞 Contacto y Soporte

Para reportar problemas o sugerencias:
```
Email: rcavieses@gmail.com
Repo: [link-al-repositorio]
```

---

**¡Disfruta consultando la literatura científica con IA!** 🚀
