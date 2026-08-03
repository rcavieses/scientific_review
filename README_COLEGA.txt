╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║                        🐟 SCIENTIFIC REVIEW RAG                           ║
║              Motor de Búsqueda Semántica para Papers Científicos         ║
║                  del Golfo de California y Pacífico Mexicano             ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝


¿QUIÉN ERES TÚ?
═════════════════════════════════════════════════════════════════════════════

Eres un colega que necesita acceder al índice RAG de papers científicos.
¡Bienvenido! Aquí encontrarás 10,500 fragmentos indexados de 429 papers
sobre ecología marina del Golfo de California.


¿CÓMO EMPEZAR? (3 pasos)
═════════════════════════════════════════════════════════════════════════════

1. INSTALAR DEPENDENCIAS
   $ pip install -r requirements.txt

2. CONFIGURAR API KEY
   Pide a tu administrador la API key de Anthropic y crea un archivo .env:
   $ echo "ANTHROPIC_API_KEY=tu-api-key" > .env

3. EJECUTAR SERVIDOR
   $ ./iniciar_rag.sh

   ¡Luego abre tu navegador en: http://localhost:8000


¿QUIÉN ES MI ADMINISTRADOR?
═════════════════════════════════════════════════════════════════════════════

La persona que te pasó este proyecto o que configuró el RAG.
Contacta con ellos si tienes problemas.


ARCHIVOS IMPORTANTES
═════════════════════════════════════════════════════════════════════════════

LEE ESTOS PRIMERO:
  • INICIO_RAPIDO.md     → Guía rápida (2 min lectura)
  • ACCESO_RAG.md        → Guía completa (10 min lectura)
  • README.md            → Documentación técnica del proyecto

PARA EJECUTAR:
  • iniciar_rag.sh       → Script que inicia el servidor
  • requirements.txt     → Dependencias Python


¿QUÉ PUEDES HACER?
═════════════════════════════════════════════════════════════════════════════

✓ Hacer consultas en lenguaje natural:
  "¿Cuál es la talla máxima del Huachinango?"
  "Parámetros biológicos de Lutjanus peru"
  "Métodos de pesca sostenible"

✓ Ver fragmentos relevantes de papers

✓ Consultar parámetros en FishBase automáticamente

✓ Obtener respuestas estructuradas con citas


EJEMPLOS DE CONSULTAS
═════════════════════════════════════════════════════════════════════════════

Biología:
  • "Talla y peso del Huachinango rojo"
  • "Ciclo reproductivo de Lutjanus peru"
  • "Dieta y hábitos alimentarios del pargo"

Ecología:
  • "Distribución de peces en el Golfo de California"
  • "Hábitat marino del Pacífico mexicano"
  • "Biodiversidad de especies marinas"

Pesquería:
  • "Métodos de captura sostenible"
  • "Impacto ambiental de la pesca"
  • "Regulación pesquera en el Golfo"


OPCIONES DE ACCESO
═════════════════════════════════════════════════════════════════════════════

1. WEB UI (Recomendado)
   $ ./iniciar_rag.sh
   → http://localhost:8000

2. LÍNEA DE COMANDOS (Interactivo)
   $ python3 scripts/phase_6_query/buscar_rag_con_fishbase.py --interactive

3. API REST (Para programadores)
   Documentación: http://localhost:8000/docs

Ver ACCESO_RAG.md para más opciones (Docker, Jupyter, etc)


¿PROBLEMAS?
═════════════════════════════════════════════════════════════════════════════

❌ "ModuleNotFoundError: No module named 'pipeline'"
   Solución: pip install -r requirements.txt

❌ "ANTHROPIC_API_KEY not found"
   Solución: Configurar .env con tu API key

❌ "Puerto 8000 ya está en uso"
   Solución: ./iniciar_rag.sh 9000  (usar otro puerto)

❌ "Lento al responder"
   Solución: Espera 10s en la primera consulta (carga el modelo)

Ver ACCESO_RAG.md sección "Troubleshooting" para más ayuda


ESPECIFICACIONES TÉCNICAS
═════════════════════════════════════════════════════════════════════════════

Índice:
  • 10,500 chunks indexados
  • 429 papers de investigación
  • Modelo de embeddings: all-MiniLM-L6-v2
  • Dimensión: 384
  • Tamaño: 40 MB

Búsqueda:
  • Algoritmo: FAISS (búsqueda vectorial)
  • Scoring: Similitud coseno
  • Top-k configurable (default: 5)

Respuesta:
  • Modelo LLM: Claude Sonnet 4.6
  • Síntesis de fragmentos: Automática
  • Citas: Automáticas


SEGURIDAD Y PRIVACIDAD
═════════════════════════════════════════════════════════════════════════════

✓ Los papers se quedan en tu máquina (no se suben a internet)
✗ Las consultas se envían a Claude API
✓ No se almacenan preguntas en base de datos
✓ Usa HTTPS si accedes desde otra máquina


SOPORTE
═════════════════════════════════════════════════════════════════════════════

Contacta al administrador del proyecto:
  Email: rcavieses@gmail.com
  (Cambia esto por tu email)


RECURSOS ÚTILES
═════════════════════════════════════════════════════════════════════════════

• INICIO_RAPIDO.md - Cómo empezar en 3 pasos
• ACCESO_RAG.md - Guía completa con 5 opciones de acceso
• README.md - Documentación técnica del proyecto completo
• http://localhost:8000/docs - API REST interactiva (Swagger)


¿LISTO?
═════════════════════════════════════════════════════════════════════════════

$ pip install -r requirements.txt
$ echo "ANTHROPIC_API_KEY=tu-api-key" > .env
$ ./iniciar_rag.sh

Luego abre: http://localhost:8000

¡A hacer preguntas! 🚀
