# 🚀 Inicio Rápido - RAG para Colegas

## 📝 En 3 pasos:

### 1️⃣ Clonar/descargar el proyecto
```bash
cd /path/a/proyecto
```

### 2️⃣ Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3️⃣ Ejecutar el servidor
```bash
./iniciar_rag.sh
```

**¡Listo!** Abre tu navegador en: **http://localhost:8000**

---

## 🌐 Acceder desde otra máquina

Pídele al administrador la dirección IP:
```
http://[IP-DEL-SERVIDOR]:8000
```

Ejemplo: `http://192.168.1.100:8000`

---

## 💡 Ejemplos de consultas

- "¿Cuál es la talla máxima del Huachinango?"
- "Parámetros biológicos de Lutjanus peru"
- "Métodos de pesca sostenible en el Golfo de California"
- "Ecología marina del Pacífico mexicano"
- "Reproducción del Huachinango rojo"

---

## ⚙️ Configuración

### Cambiar puerto (si 8000 está ocupado)
```bash
./iniciar_rag.sh 8080
```

### Modo interactivo (sin web UI)
```bash
set -a && source .env && set +a
PYTHONPATH=. python3 scripts/phase_6_query/buscar_rag_con_fishbase.py --interactive
```

---

## 📚 Más información

Ver `ACCESO_RAG.md` para opciones avanzadas como:
- API REST programática
- Docker
- Jupyter Notebook
- SSH tunneling para acceso remoto

---

## 🆘 Problemas?

1. **"No se encuentra .env"** → Crea un archivo `.env` con tu ANTHROPIC_API_KEY
2. **Puerto ocupado** → Cambia de puerto: `./iniciar_rag.sh 9000`
3. **Sin internet** → Necesitas conectarte (para Claude API)
4. **Lento** → Espera a que cargue el modelo (~10 segundos al iniciar)

---

**¿Preguntas?** Contacta al administrador del proyecto.
