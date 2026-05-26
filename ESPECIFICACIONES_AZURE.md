# Especificaciones de Azure para Indexación en 6 Días

## CÁLCULO DE REQUISITOS

### Volumen de Trabajo
```
Indexación actual:      42,200 PDFs      (en curso)
Búsqueda pendiente:     8,330 especies   (en curso)
PDFs esperados:         ~30-50K más      (después de búsqueda)
───────────────────────────────────────
TOTAL PROYECTADO:       ~70-100K PDFs

PROMEDIO: ~85,000 PDFs para indexar
```

### Velocidad Actual vs Requerida

**Velocidad actual:**
```
Provider:        Local (SentenceTransformers)
Velocidad:       25 PDFs/hora
Workers:         4 paralelos
Máquina:         1 local (dataserver02)

Tiempo para 85K: 85,000 ÷ 25 = 3,400 horas = 142 días
```

**Velocidad requerida (6 días):**
```
Tiempo disponible:  6 días × 24 horas = 144 horas
PDFs a procesar:    85,000
Velocidad requerida: 85,000 ÷ 144 = 590 PDFs/hora

Factor de aceleración: 590 ÷ 25 = 23.6× más rápido
```

### ¿Cómo lograr 590 PDFs/hora?

**Opción A: Una sola VM gigante**
```
590 PDFs/hora ÷ 25 PDFs/hora por worker = 23.6 workers

Necesitarías:
- 24 CPUs (1 CPU por worker + overhead)
- 96 GB RAM (4 GB por worker × 24)
- Costo: ~$10-15/día en Azure (muy caro)
- Problema: FAISS no escala bien en una sola máquina
```

**Opción B: Múltiples VMs medianas (RECOMENDADO)** ⭐
```
3 VMs × 8 workers = 24 workers
24 workers × 25 PDFs/hora = 600 PDFs/hora ✓

Especificaciones por VM:
├─ vCPUs:        8
├─ RAM:          16 GB
├─ Disco:        256 GB (SSD)
└─ Costo:        ~$2-3/día cada una

TOTAL: 3 VMs = $6-9/día × 6 días = $36-54 USD

O aumentar a 4 VMs si quieres margen de seguridad:
├─ 4 VMs × 6 CPUs = 24 workers
├─ Velocidad: ~600 PDFs/hora
├─ Costo: ~$8-12/día × 6 días = $48-72 USD
└─ Más tolerancia a fallos
```

**Opción C: Máquina grande + 1 paralela (Balance)**
```
Máquina Principal (Azure):
├─ vCPUs:        16
├─ RAM:          32 GB
├─ Disco:        512 GB (SSD)
├─ Workers:      12
└─ Costo:        ~$4-5/día

Máquina Paralela (Opcional):
├─ vCPUs:        8
├─ RAM:          16 GB
├─ Disco:        256 GB (SSD)
├─ Workers:      8
└─ Costo:        ~$2-3/día

TOTAL: ~$6-8/día × 6 días = $36-48 USD
VELOCIDAD: (12 + 8) × 25 = 500 PDFs/hora
```

---

## RECOMENDACIÓN: Opción B (3 VMs)

### Configuración Óptima para Azure

```
┌─────────────────────────────────────────────────────────────┐
│  MÁQUINA VIRTUAL #1, #2, #3 (Idénticas)                    │
├─────────────────────────────────────────────────────────────┤
│  SKU Azure:              Standard_D8s_v3 o similar          │
│  vCPUs:                  8 (intel Xeon)                     │
│  RAM:                    16 GB DDR4                         │
│  Disco:                  256 GB SSD Premium (P10)           │
│  SO:                     Ubuntu 22.04 LTS                   │
│  Región:                 Cercana a tus datos (latencia)     │
│  Red:                    VNet privada + Load Balancer       │
│  Almacenamiento:         Azure Blob Storage (PDFs)          │
├─────────────────────────────────────────────────────────────┤
│  COSTO MENSUAL (on-demand):                                 │
│  • 3 VMs × $120/mes = $360/mes                              │
│  • Para 6 días = $72 USD                                    │
│  • Para 1 mes = $360 USD                                    │
│                                                              │
│  COSTO CON RESERVA 1 AÑO: -40% → $216/mes = $26/6días      │
└─────────────────────────────────────────────────────────────┘
```

### Detalle de Especificaciones

| Componente | Cantidad | Justificación |
|-----------|----------|---------------|
| **vCPU** | 8 | 1 CPU/worker (8 workers × 1 CPU = 8 vCPU) |
| **RAM** | 16 GB | 2 GB base OS + 2 GB × 8 workers = 16 GB |
| **Disco** | 256 GB | 50 GB SO + 200 GB para índice FAISS temp |
| **SSD Premium** | Sí | I/O crítico: muchas lecturas de PDFs |
| **Network** | Gigabit | Comunicación entre VMs para fusión índices |

### Performance Esperada

```
Velocidad de indexación:

Por VM:
  • 8 workers en paralelo
  • 25 PDFs/hora por worker
  • = 200 PDFs/hora por VM

Total (3 VMs):
  • 3 × 200 = 600 PDFs/hora
  • 85,000 PDFs ÷ 600 = 142 horas
  • ≈ 6 días (con overhead de fusión) ✓

Por día:
  • 600 PDFs/hora × 24 horas = 14,400 PDFs/día
  • 85,000 ÷ 14,400 = 5.9 días ✓
```

---

## ARQUITECTURA EN AZURE

```
┌─────────────────────────────────────────────────────────────┐
│                    AZURE BLOB STORAGE                       │
│              (PDFs: 50+ GB en contenedores)                 │
└────────────┬────────────────────────┬──────────────┬────────┘
             │                        │              │
   ┌─────────▼──────────┐  ┌─────────▼──────┐  ┌──────▼──────┐
   │  VM #1 (8 vCPU)    │  │  VM #2 (8 vCPU)│  │ VM #3 (8 vCP│
   │  16 GB RAM         │  │  16 GB RAM     │  │ 16 GB RAM   │
   │  200 PDFs/hora     │  │  200 PDFs/hora │  │ 200 PDFs/h. │
   │                    │  │                │  │             │
   │ • indexar_paralelo │  │ • indexar_par. │  │ • indexar_p.│
   │ • 8 workers (batch│  │ • 8 workers    │  │ • 8 workers │
   │   1-1500)          │  │  (batch 1501-) │  │  (batch...)  │
   │ • rag_index_temp_1 │  │ • rag_index_..2│  │ • rag_index_3
   └────────────┬───────┘  └────────┬───────┘  └───────┬──────┘
                │                   │                  │
                └───────────────────┼──────────────────┘
                                    │
                          ┌─────────▼────────┐
                          │ Orquestador      │
                          │ (Script maestro) │
                          │ • Distribuye     │
                          │   batches        │
                          │ • Monitorea      │
                          │ • Fusiona índices│
                          │ • Resultado:     │
                          │   rag_index/     │
                          └──────────────────┘
```

---

## OPCIÓN ALTERNATIVA: Spot VMs (Más Barato)

Si quieres ahorrar:

```
Azure Spot VMs (3 unidades):
• 70% descuento vs on-demand
• Especificaciones: Iguales (8 vCPU, 16 GB)
• Riesgo: Pueden interrumpirse si Azure lo requiere
• Costo: $72 USD × 0.3 = $21.60 para 6 días ⭐

Recomendación:
- Para 6 días críticos: ON-DEMAND ($72)
- Si tienes margen tiempo: SPOT ($22) pero con respaldo
```

---

## PLAN DE IMPLEMENTACIÓN (Día 1)

### 1. Crear VMs en Azure (30 min)
```bash
# Resource Group
az group create --name scientific-review-rg --location eastus

# VM #1, #2, #3 (repetir 3 veces)
az vm create \
  --resource-group scientific-review-rg \
  --name indexer-vm-1 \
  --image UbuntuLTS \
  --size Standard_D8s_v3 \
  --admin-username azureuser \
  --generate-ssh-keys
```

### 2. Configurar VMs (1 hora)
```bash
# En cada VM:
- Instalar Python 3.11 + venv
- Clonar repositorio
- Instalar dependencias (sentence-transformers, faiss, etc.)
- Montar Azure Blob Storage como /mnt/pdfs
```

### 3. Distribuir Batches (15 min)
```
VM #1: Procesa batches 1-32 (1,500 especies)
VM #2: Procesa batches 33-64 (1,500 especies)
VM #3: Procesa batches 65-95 (1,700 especies)
```

### 4. Ejecutar en Paralelo (6 días)
```bash
# En cada VM simultáneamente:
python3 indexar_paralelo.py --batch-start X --batch-end Y

# Monitorear progreso centralizado:
watch -n 300 'tail -5 indexer-vm-{1,2,3}/indexar_paralelo.log'
```

### 5. Fusionar Índices (30 min - Día 6)
```bash
# Script que:
- Descarga índices temporales de cada VM
- Fusiona en FAISS
- Resultado final: outputs/rag_index/
```

---

## COSTOS TOTALES

| Escenario | Costo 6 días | Costo 30 días |
|-----------|------------|--------------|
| 3 VMs on-demand | $72 | $360 |
| 3 VMs spot (risky) | $22 | $108 |
| 1 VM grande (16 vCPU) | $48 | $240 |
| Hybrid (1 local + 1 Azure) | $36 | $180 |

**RECOMENDACIÓN:** 3 VMs on-demand = $72 por seguridad

---

## CHECKLIST PRE-IMPLEMENTACIÓN

- [ ] ¿Tienes suscripción Azure activa?
- [ ] ¿Cuota de vCPUs suficiente? (necesitas 24 vCPUs)
- [ ] ¿Storage para PDFs? (50+ GB recomendado)
- [ ] ¿Networking configurado? (VNet entre VMs)
- [ ] ¿Script de orquestación listo?
- [ ] ¿Backup de código y datos?

---

## TIEMPO TOTAL

| Fase | Tiempo |
|------|--------|
| Crear VMs en Azure | 30 min |
| Configurar SO y dependencias | 1 hora |
| Distribuir código y batches | 15 min |
| Ejecutar indexación | **5-6 días** |
| Fusionar índices finales | 30 min |
| **TOTAL** | **~6 días** ✓ |

---

**¿Quieres que implemente el script de orquestación para Azure?**
