# 🔌 Acceso RAG con VS Code Port Forwarding

**Para administrador + colegas que usan VS Code**

---

## 🎯 Objetivo

Acceder al servidor RAG remoto de forma segura a través de VS Code, sin exponer puertos públicamente.

---

## 👨‍💻 PARA EL ADMINISTRADOR (tú)

### Paso 1: Asegúrate que el servidor está ejecutándose

```bash
cd /home/atlantis/scientific_review
./iniciar_rag.sh
```

Deberías ver:
```
RAG Engine inicializado
Dirección: http://0.0.0.0:8000
```

**Mantén este terminal abierto** (el servidor debe estar corriendo)

### Paso 2: Verificar que funciona localmente (opcional)

```bash
# En otra terminal del servidor:
curl http://localhost:8000/api/health
```

Respuesta esperada:
```json
{"status": "ok", "rag_initialized": true}
```

### Paso 3: Compartir instrucciones con colegas

Envíales el archivo `VSCODE_COLEGA_ACCESO.md` (abajo)

---

## 👥 PARA TUS COLEGAS

Envía este contenido a tus colegas:

---

### 🚀 GUÍA RÁPIDA: Acceder a RAG desde VS Code

**Requisitos:**
- VS Code instalado
- Extensión "Remote - SSH" instalada
- Credenciales SSH del servidor

**3 pasos:**

#### 1. Conectar al servidor

- Abre VS Code
- Ctrl+Shift+P
- Busca: "Remote-SSH: Connect to Host..."
- Ingresa: `atlantis@tu-servidor.com`
  
  (Pide IP/nombre al administrador)

- Presiona Enter
- Confirma la huella SSH si aparece
- Espera a que se reconecte

#### 2. Abrir terminal en el servidor

- En VS Code (ahora verás "SSH: ..." en la esquina inferior)
- Terminal → New Terminal (o Ctrl+`)
- Deberías estar en `/home/atlantis/scientific_review`

Verifica:
```bash
pwd
# Debe mostrar: /home/atlantis/scientific_review
```

#### 3. Activar Port Forwarding

**Opción A: Automático (Recomendado)**
- En VS Code, haz clic en la esquina inferior izquierda donde dice "SSH: ..."
- Click en "Remote" → "Ports"
- Click en "+ Forward Port"
- Ingresa: `8000`
- Presiona Enter
- ¡Listo! Verás `localhost:8000` en la lista

**Opción B: Manual**
- Ctrl+Shift+P
- "Forward a Port"
- Ingresa: `8000`
- Presiona Enter

#### 4. Acceder a la interfaz

En tu navegador, abre:
```
http://localhost:8000
```

¡Ya estás conectado al servidor remoto! 🎉

---

## ✨ Ventajas

✓ **Seguro:** Cifrado con SSH  
✓ **Privado:** No expone puertos públicos  
✓ **Fácil:** Todo en VS Code  
✓ **Rápido:** ~5 minutos para configurar  
✓ **Confiable:** Conexión estable  

---

## 📝 Ejemplos de consultas

Una vez en http://localhost:8000:

```
"¿Cuál es la talla máxima del Huachinango?"
"Parámetros biológicos de Lutjanus peru"
"Métodos de pesca sostenible"
"Ecología del Golfo de California"
```

---

## 🆘 Problemas comunes

**P: "Connection refused"**
- Verifica que el servidor esté corriendo (pregunta al admin)
- Que el puerto forwarding esté configurado (ves `localhost:8000`?)

**P: "Permission denied (publickey)"**
- Verifica tu SSH key: `ssh -v atlantis@servidor`
- Pide al admin que verifique tus permisos

**P: "Timeout"**
- Verifica conexión a internet
- El servidor puede estar lento (espera ~10s en primera consulta)

**P: "No hay opción de 'Ports'"**
- Ctrl+Shift+P → "Remote-SSH: Focus on Remote Window"
- Luego Ctrl+Shift+P → "Focus on Ports View"

---

## 📞 Contacto

Si tienes problemas:
1. Verifica que estés conectado (ves "SSH: ..." en esquina inferior)
2. Que el port forwarding esté activo (ves `localhost:8000` en Ports)
3. Contacta al administrador: rcavieses@gmail.com

---

## 🔍 Verificación rápida

¿No sabes si está funcionando? Prueba esto:

```bash
# En terminal de VS Code (conectado al servidor):
curl http://localhost:8000/api/health

# Si ves: {"status":"ok"} → ¡Funciona!
```

---

**¡Disfruta usando RAG!** 🐟

---

## 📚 Más información

- Ver documentación completa: `ACCESO_RAG.md`
- Guía rápida: `INICIO_RAPIDO.md`
- Para administrador: `VSCODE_PORT_FORWARDING.md`
