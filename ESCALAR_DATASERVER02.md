# Escalar dataserver02 para 6 Días

## ANÁLISIS: ¿Escalar o Crear VMs Nuevas?

### Información Necesaria

Para darte la recomendación exacta, necesito saber:
```
1. ¿Qué SKU actual tiene dataserver02?
   (Ej: Standard_D8s_v3, Standard_D16s_v3, etc.)

2. ¿Cuántos vCPUs tiene ahora?
   (Puedo verificar con: nproc)

3. ¿Cuánta RAM tiene?
   (Puedo verificar con: free -h)

4. ¿Cuánto cuesta mensualmente?
```

Mientras verifico, te muestro el análisis teórico:

---

## ESCENARIO 1: dataserver02 Actual = D8s_v3

```
Specs actuales (probable):
├─ vCPUs:      8
├─ RAM:        16 GB
├─ Costo:      ~$160/mes
└─ Workers:    4 (configuración actual)

PARA 6 DÍAS NECESITAS:
├─ vCPUs:      24 (3× más)
├─ RAM:        48-64 GB (4× más)
├─ Costo:      ~$400-450/mes
└─ Workers:    24 paralelos
```

### Opción A: Escalar a D32s_v3
```
Nueva configuración:
├─ vCPUs:      32 (4× más que actual)
├─ RAM:        64 GB (4× más)
├─ Disco:      Aumentar a 512 GB
├─ Costo:      ~$480/mes
├─ Para 6 días: ~$96 USD
└─ Tiempo downtime: 5-10 min (redimensionar + reiniciar)

Ventajas:
✅ Sin cambios de arquitectura
✅ Mismo firewall, IPs, configuración
✅ Solo 1 máquina a administrar
✅ No duplicas datos (PDFs/índices)
✅ Más simple de implementar

Desventajas:
❌ Más caro que 3 VMs medianas ($96 vs $72)
❌ "Overkill" = pagas más por más poder del que necesitas


### Opción B: Escalar a D24s_v3 (Más Balance)
```
Nueva configuración:
├─ vCPUs:      24 (3× más que actual)
├─ RAM:        48 GB (3× más)
├─ Disco:      512 GB
├─ Costo:      ~$360/mes
├─ Para 6 días: ~$72 USD (IGUAL que 3 VMs)
└─ Velocidad:   600 PDFs/hora ✓

Ventajas:
✅ Costo IGUAL a 3 VMs
✅ Exactamente la velocidad que necesitas
✅ Una sola máquina = fácil de administrar
✅ Misma arquitectura local, sin cambios


---

## COMPARATIVA: Escalar vs Crear VMs

| Aspecto | Escalar D24s_v3 | 3 VMs D8s_v3 |
|--------|---|---|
| **Velocidad** | 600 PDFs/h ✓ | 600 PDFs/h ✓ |
| **Costo 6 días** | $72 | $72 |
| **Implementación** | 10 min | 1.5 horas |
| **Complejidad** | Mínima | Alta |
| **Downtime** | 5-10 min | 0 min |
| **Redundancia** | No | Sí (3 máquinas) |
| **Escalabilidad futura** | Limitada (max D64s) | Infinita |
| **Administración** | 1 máquina | 3 máquinas |

---

## RECOMENDACIÓN

### Para 6 días específicos: **Escala dataserver02 a D24s_v3** ⭐⭐⭐

**Razones:**
1. ✅ **Exactamente lo que necesitas**: 24 vCPUs = 600 PDFs/hora
2. ✅ **Costo idéntico**: $72 por 6 días (igual a 3 VMs)
3. ✅ **Implementación rápida**: 10 minutos de downtime
4. ✅ **Sin cambios arquitectónicos**: Mismo código, misma configuración
5. ✅ **Monitoreo simple**: Una sola máquina
6. ✅ **Datos centralizados**: No necesitas sincronizar entre VMs

**Única desventaja:** Sin redundancia (si falla, pierdes todo)
- **Mitigation:** Hacer backup antes (1 hora)

---

## PASOS PARA ESCALAR

### Paso 1: Backup (30 min)
```bash
# Hacer snapshot del disco de dataserver02
# En Azure Portal:
# VM → Disks → Create Snapshot
# Esperar a que complete

# O línea de comandos:
az snapshot create \
  --resource-group tu-rg \
  --name dataserver02-backup-$(date +%Y%m%d) \
  --source $(az vm show -d --resource-group tu-rg --name dataserver02 --query sourceImageId)
```

### Paso 2: Redimensionar VM (5-10 min downtime)
```bash
# Detener VM
az vm deallocate \
  --resource-group tu-rg \
  --name dataserver02

# Cambiar tamaño a D24s_v3
az vm resize \
  --resource-group tu-rg \
  --name dataserver02 \
  --size Standard_D24s_v3

# Reiniciar VM
az vm start \
  --resource-group tu-rg \
  --name dataserver02

# Verificar nuevas specs
ssh dataserver02
nproc          # Debería mostrar 24
free -h        # Debería mostrar ~48GB
```

### Paso 3: Actualizar Configuration
```bash
# En dataserver02, editar indexar_paralelo.py:
MAX_WORKERS = 24  # Cambiar de 4 a 24

# Reiniciar proceso
killall python 2>/dev/null || true
nohup python3 indexar_paralelo.py > indexar_paralelo.log 2>&1 &
```

---

## TIMING DE ESCALA

```
Tiempo actual de indexación: ~10-15 días (4 workers)
Después de escalar a 24 workers: ~6 días ✓

Cálculo:
42,200 PDFs ÷ 25 PDFs/hora × 4 workers = 10.5 días
42,200 PDFs ÷ 25 PDFs/hora × 24 workers = 1.75 días (solo actual)

+ Búsqueda + descarga nuevos PDFs (+30-40K)
+ Overhead de sistema
= ~6 días realista
```

---

## COSTOS DETALLADOS (Escala a D24s_v3)

### Opción 1: Pay-as-you-go
```
Standard_D24s_v3: ~$360/mes
6 días: ($360/30) × 6 = $72 USD

+ Almacenamiento disco (1 TB): ~$15/mes → ~$3 para 6 días
+ Ancho banda (mínimo): ~$1

TOTAL: ~$76 USD (6 días)
```

### Opción 2: Reserved Instance (Si lo dejas 1 mes)
```
D24s_v3 con reserva 1 año: ~$200/mes (-44% descuento)
1 mes completo: $200
6 días: ~$40
```

### Opción 3: Spot (Riesgoso)
```
D24s_v3 Spot: ~$100/mes (-70% descuento)
6 días: ~$20

⚠️ Riesgo: Azure puede interrumpir si necesita recursos
```

---

## PARÁMETROS DE ESCALA

Según tu objetivo de 6 días:

| Objetivo | SKU | vCPUs | RAM | Costo 6d | Workers |
|----------|-----|-------|-----|---------|---------|
| 6 días (ajustado) | **D24s_v3** | **24** | **48GB** | **$72** | **24** |
| 4 días (urgente) | D32s_v3 | 32 | 64GB | $96 | 32 |
| 8 días (relajado) | D16s_v3 | 16 | 32GB | $48 | 16 |

**RECOMENDACIÓN: D24s_v3** - Exactamente 6 días, costo óptimo

---

## SIMULACIÓN DE RENDIMIENTO

```
Después de escalar a D24s_v3:

Especificaciones:
├─ 24 vCPUs
├─ 48 GB RAM
├─ 8 workers × 3 = 24 workers paralelos
└─ 25 PDFs/hora por worker

Velocidad:
├─ 24 workers × 25 PDFs/h = 600 PDFs/hora
├─ 600 PDFs/h × 24 h = 14,400 PDFs/día
├─ 85,000 PDFs ÷ 14,400 = 5.9 días
└─ ✓ DENTRO DEL TARGET (6 días)

Por worker:
├─ CPU: ~40-50% utilización (buen balance)
├─ RAM: 2 GB por worker × 24 = 48 GB (full)
├─ Disco: Lectura constante (SSD necesario)
└─ Red: Mínima (todo local)
```

---

## PLAN DE EJECUCIÓN (RECOMENDADO)

### Día 1 (Hoy)
```
10:00 - Hacer snapshot de dataserver02 (seguridad)
10:15 - Parar procesos actuales
        killall python
10:20 - Redimensionar a D24s_v3 (5-10 min downtime)
10:30 - Verificar specs (nproc, free -h)
10:35 - Actualizar MAX_WORKERS = 24
10:40 - Reiniciar indexar_paralelo.py
10:45 - Monitorear primeros 30 min

Resultado: Indexación corre a 600 PDFs/hora ✓
```

### Días 2-6
```
Monitorear diariamente:
├─ 10,000+ PDFs/día esperado
├─ Si hay errores, ajustar workers (24 → 20)
└─ Si va rápido, mantener
```

### Día 6 (Noche)
```
Fusionar índices finales
Resultado: rag_index/ completo
```

---

## CHECKLIST PRE-ESCALA

- [ ] ¿Confirmar que dataserver02 es VM en Azure?
- [ ] ¿Verificar SKU actual? (nproc, free -h)
- [ ] ¿Hacer snapshot de seguridad?
- [ ] ¿Backup de código y datos?
- [ ] ¿Confirmar cuota de vCPUs en Azure?
- [ ] ¿Detener procesos antes de redimensionar?
- [ ] ¿Actualizar MAX_WORKERS a 24?

---

**¿Procedemos a escalar dataserver02?**

Si dices que sí, necesito:
1. Confirmar SKU actual
2. Hacer el redimensionamiento
3. Ajustar configuración a 24 workers
4. Reiniciar procesos

Todo en ~30 minutos de trabajo ✓
