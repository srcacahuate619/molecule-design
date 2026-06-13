# 🔍 AUDITORÍA DE CÓDIGO - MolDesign AI
**Fecha:** 9 de junio de 2026  
**Versión:** v6.4  
**Auditor:** Análisis automatizado completo

---

## 📋 RESUMEN EJECUTIVO

### ✅ Fortalezas Identificadas
- **Arquitectura sólida**: Separación clara de responsabilidades (API, Workers, ML)
- **Documentación excelente**: Código bien comentado y con docstrings
- **Manejo de errores robusto**: Sistema de excepciones personalizado bien estructurado
- **Validación científica**: Pipeline de validación química riguroso
- **Trazabilidad**: Sistema de logging estructurado y reproducibilidad con seeds

### ⚠️ PROBLEMAS CRÍTICOS ENCONTRADOS

#### 🔴 **CRÍTICO 1: Credenciales expuestas en .env**
**Archivo:** `backend/.env` (líneas 10, 14, 22, 29, 32, 35)

```env
SECRET_KEY=f593044d113149aad7277fdbbe7e38f6a09f2a49e5e97a6c822b02616b6166c9
DATABASE_URL=postgresql+asyncpg://admin:Johan619.@192.168.1.64:5432/moldesign_db
MINIO_SECRET_KEY=Johan619.
GEMINI_API_KEY=AIzaSyDMatUdVHZ2nvbpQwHXW14ryNtagbPb3-o
VERCEL_TOKEN=vcp_1SrSQVqrJn77FyHGi9cisGZNSiBd2xH7Cf
SOLANA_PRIVATE_KEY=28359c59a54c719a64a2314b176895da16c0b3e4badb10c968ad32d09faeeb70...
```

**Impacto:** 🔴 **CRÍTICO - SEGURIDAD COMPROMETIDA**
- Contraseñas de base de datos expuestas
- API keys de servicios externos (Gemini, Vercel) comprometidas
- Private key de Solana blockchain expuesta (acceso a fondos)
- Secret key de JWT expuesta (permite falsificar tokens)

**Acción Inmediata Requerida:**
1. ✅ **ROTAR TODAS LAS CREDENCIALES INMEDIATAMENTE**
2. Revocar el token de Vercel en el dashboard
3. Deshabilitar la API key de Gemini y generar una nueva
4. Generar nueva wallet de Solana y transferir fondos
5. Cambiar contraseñas de PostgreSQL y MinIO
6. Regenerar SECRET_KEY con `openssl rand -hex 32`
7. Verificar si el archivo .env fue commiteado a git (revisar historial)
8. Si fue commiteado, considerar el repositorio comprometido

**Prevención:**
```bash
# Agregar a .gitignore (verificar que ya esté)
echo "backend/.env" >> .gitignore
echo ".env" >> .gitignore

# Usar .env.example como plantilla
cp backend/.env backend/.env.example
# Reemplazar valores reales con placeholders en .env.example
```

---

#### 🔴 **CRÍTICO 2: Bare except clauses (Silent failures)**
**Archivos afectados:**
- `backend/utils/structural.py:76` - Parsing de coordenadas PDB
- `backend/services/docking/vina_service.py:multiple` - Procesamiento de docking
- `backend/services/denovo/generator.py:multiple` - Generación de sugerencias

```python
# ❌ MAL - Oculta todos los errores
try:
    x = float(line[30:38])
    y = float(line[38:46])
    z = float(line[46:54])
except:
    continue

# ✅ BIEN - Captura específica con logging
try:
    x = float(line[30:38])
    y = float(line[38:46])
    z = float(line[46:54])
except (ValueError, IndexError) as e:
    log.warning("failed_to_parse_coordinates", line=line[:80], error=str(e))
    continue
```

**Impacto:** 🔴 **ALTO**
- Errores silenciosos que pueden causar resultados incorrectos
- Debugging extremadamente difícil
- Puede ocultar bugs críticos en producción

**Solución:**
Reemplazar todos los `except:` con excepciones específicas y logging apropiado.

---

#### 🟡 **ALTO 3: SQL Injection potencial en scripts**
**Archivos:** `backend/inspect_db.py:multiple`, `backend/check_last_evals.py`

```python
# ⚠️ VULNERABLE - String interpolation en SQL
res2 = await c.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name='{eval_table}' AND table_schema='public'"))
```

**Impacto:** 🟡 **MEDIO** (solo en scripts de desarrollo, no en producción)
- Aunque estos son scripts de desarrollo, establecen mal precedente
- Si se copia el patrón a código de producción, sería crítico

**Solución:**
```python
# ✅ CORRECTO - Usar parámetros
res2 = await c.execute(
    text("SELECT column_name FROM information_schema.columns WHERE table_name=:table AND table_schema='public'"),
    {"table": eval_table}
)
```

---

#### 🟡 **ALTO 4: Rate Limiter en memoria (no escalable)**
**Archivo:** `backend/api/rate_limiter.py`

**Problema:**
- Estado en memoria: no compartido entre workers/procesos
- No sobrevive reinicios
- Inefectivo con múltiples instancias (load balancer)

**Documentación del código:**
```python
# Limitaciones conocidas:
# - Estado en memoria: no compartido entre workers/procesos.
# - IPs detrás de proxy: depende de que el proxy setee X-Forwarded-For
# - No sobrevive reinicios del servidor.
```

**Impacto:** 🟡 **MEDIO**
- Protección anti-brute-force inefectiva en producción multi-worker
- Atacante puede bypassear límites reiniciando conexión a otro worker

**Solución:**
```python
# Migrar a Redis-based rate limiting
import redis.asyncio as redis

class RedisRateLimiter:
    async def check(self, request: Request) -> None:
        ip = self._get_client_ip(request)
        key = f"ratelimit:{ip}"
        
        # Atomic increment with expiry
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.window_seconds)
        count, _ = await pipe.execute()
        
        if count > self.max_requests:
            raise HTTPException(status_code=429, ...)
```

---

#### 🟡 **ALTO 5: Debug code en producción**
**Archivo:** `backend/services/docking/vina_service.py:line ~300`

```python
# DEBUG: Bypass cache completely for all jobs (force recompute every time)
cached = None
```

**Impacto:** 🟡 **MEDIO**
- Cache deshabilitado = performance degradada
- Costo computacional innecesario
- Puede causar timeouts bajo carga

**Solución:**
Remover código de debug o usar feature flag:
```python
if settings.is_development and settings.bypass_docking_cache:
    cached = None
```

---

#### 🟢 **MEDIO 6: Uso excesivo de print() en lugar de logging**
**300+ ocurrencias** en scripts de backend

**Problema:**
- No se captura en logs estructurados
- No tiene niveles (INFO, WARNING, ERROR)
- Dificulta debugging en producción

**Solución:**
```python
# ❌ MAL
print(f"Procesando {pdb_id}...")

# ✅ BIEN
log.info("processing_target", pdb_id=pdb_id)
```

---

#### 🟢 **MEDIO 7: innerHTML en frontend**
**Archivo:** `frontend/components/interfaces/pro/AdvancedMolstarViewer.tsx`

```typescript
containerRef.current.innerHTML = "";
```

**Impacto:** 🟢 **BAJO** (uso legítimo para limpiar contenedor)
- En este caso específico es seguro (limpieza de contenedor)
- Pero establece precedente peligroso

**Recomendación:**
```typescript
// Más explícito y seguro
while (containerRef.current.firstChild) {
    containerRef.current.removeChild(containerRef.current.firstChild);
}
```

---

#### 🟢 **MEDIO 8: CORS configurado con wildcard en producción**
**Archivo:** `docker-compose.yml:68`

```yaml
CORS_ORIGINS: '["*"]'
```

**Impacto:** 🟢 **BAJO-MEDIO**
- Permite requests desde cualquier origen
- Puede facilitar ataques CSRF si no hay otras protecciones

**Solución:**
```yaml
# En producción, especificar dominios exactos
CORS_ORIGINS: '["https://molecule-design.vercel.app"]'
```

---

## 🔧 DEUDAS TÉCNICAS IDENTIFICADAS

### 1. **Autenticación JWT custom (reinventar la rueda)**
**Archivo:** `backend/api/auth.py`

**Problema:**
- Implementación manual de JWT en lugar de usar biblioteca probada
- Mayor superficie de ataque
- Más difícil de mantener

**Recomendación:**
```python
# Usar biblioteca estándar
from jose import jwt, JWTError
# o
from python-jose import jwt
```

**Justificación del código actual:**
> "Implementamos un JWT HS256 mínimo usando solo stdlib para mantener el backend autocontenido."

**Evaluación:** Aunque funcional, no es best practice para producción.

---

### 2. **Falta de índices de base de datos documentados**
**Problema:**
- No hay migraciones SQL visibles
- No se documentan índices necesarios para queries frecuentes
- Puede causar performance issues a escala

**Queries que necesitan índices:**
```sql
-- Búsquedas frecuentes en evaluation_results
CREATE INDEX idx_eval_target_pdb ON evaluation_results(target_pdb_id);
CREATE INDEX idx_eval_created_at ON evaluation_results(created_at DESC);
CREATE INDEX idx_eval_task_id ON evaluation_results(task_id);

-- Búsquedas en molecules
CREATE INDEX idx_mol_smiles_hash ON molecules(smiles_hash);
CREATE INDEX idx_mol_status ON molecules(status);
```

---

### 3. **Falta de tests automatizados**
**Observación:**
- Existen tests en `backend/tests/` pero no hay evidencia de CI/CD
- No hay coverage reports
- Tests de integración requieren setup manual

**Recomendación:**
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

---

### 4. **Manejo de secretos en Docker Compose**
**Archivo:** `docker-compose.yml`

**Problema:**
- Variables de entorno en texto plano
- No usa Docker secrets

**Solución:**
```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt
  
services:
  api:
    secrets:
      - db_password
    environment:
      DATABASE_PASSWORD_FILE: /run/secrets/db_password
```

---

### 5. **Falta de health checks en workers**
**Archivo:** `docker-compose.yml:90-110`

**Problema:**
- Worker de Celery no tiene healthcheck
- Si el worker muere silenciosamente, las tareas se acumulan

**Solución:**
```yaml
worker:
  healthcheck:
    test: ["CMD-SHELL", "celery -A api.celery_app inspect ping -d celery@$$HOSTNAME"]
    interval: 30s
    timeout: 10s
    retries: 3
```

---

### 6. **Timeout de docking muy alto (600s)**
**Archivo:** `backend/services/docking/vina_service.py:232`

```python
stdout_bytes, stderr_bytes = await asyncio.wait_for(
    process.communicate(), timeout=600.0  # 10 minutos
)
```

**Problema:**
- 10 minutos es excesivo para una operación interactiva
- Puede causar acumulación de workers bloqueados
- Usuario esperando demasiado tiempo

**Recomendación:**
- Timeout de 120s para moléculas normales
- Queue separada para moléculas complejas con timeout mayor
- Implementar cancelación de tareas

---

### 7. **Falta de monitoreo y alertas**
**Observación:**
- No hay integración con sistemas de monitoreo (Prometheus, Grafana)
- No hay alertas configuradas
- Flower está en profile dev (no en producción)

**Recomendación:**
```python
# Agregar métricas con prometheus-client
from prometheus_client import Counter, Histogram

docking_duration = Histogram('docking_duration_seconds', 'Time spent in docking')
docking_failures = Counter('docking_failures_total', 'Total docking failures')
```

---

## 📊 MÉTRICAS DE CALIDAD DEL CÓDIGO

### Complejidad
- ✅ **Buena separación de concerns**
- ✅ **Funciones bien documentadas**
- ⚠️ **Algunos archivos muy largos** (vina_service.py: 638 líneas)

### Seguridad
- 🔴 **Credenciales expuestas** (CRÍTICO)
- 🟡 **Rate limiting débil**
- ✅ **Validación de entrada robusta**
- ✅ **Uso de prepared statements en ORM**

### Performance
- ⚠️ **Cache de docking deshabilitado en debug**
- ⚠️ **Falta de índices documentados**
- ✅ **Uso de async/await apropiado**
- ✅ **Connection pooling configurado**

### Mantenibilidad
- ✅ **Excelente documentación inline**
- ✅ **Logging estructurado**
- ⚠️ **300+ print statements en scripts**
- ⚠️ **Bare except clauses**

---

## 🎯 PLAN DE ACCIÓN PRIORIZADO

### 🔴 INMEDIATO (Hoy)
1. **Rotar todas las credenciales expuestas**
2. **Verificar si .env fue commiteado a git**
3. **Remover código de debug en producción**

### 🟡 CORTO PLAZO (Esta semana)
4. **Reemplazar bare except con excepciones específicas**
5. **Migrar rate limiter a Redis**
6. **Agregar índices de base de datos**
7. **Configurar health checks para workers**

### 🟢 MEDIANO PLAZO (Este mes)
8. **Reemplazar print() con logging en scripts**
9. **Implementar CI/CD con tests automatizados**
10. **Agregar monitoreo con Prometheus**
11. **Documentar migraciones de base de datos**
12. **Considerar migrar JWT a biblioteca estándar**

### 🔵 LARGO PLAZO (Próximo trimestre)
13. **Implementar Docker secrets**
14. **Agregar coverage de tests >80%**
15. **Implementar cancelación de tareas largas**
16. **Refactorizar archivos muy largos**

---

## ✅ ASPECTOS POSITIVOS DESTACABLES

1. **Arquitectura científica sólida**: El pipeline de validación química es robusto
2. **Documentación excepcional**: Comentarios claros explicando decisiones
3. **Manejo de errores**: Sistema de excepciones personalizado bien diseñado
4. **Reproducibilidad**: Uso de seeds y versionado de herramientas
5. **Separación de concerns**: Microservicios bien definidos
6. **Async/await**: Uso correcto de programación asíncrona
7. **Type hints**: Buen uso de anotaciones de tipo en Python
8. **Validación de entrada**: Validación rigurosa con Pydantic

---

## 📝 CONCLUSIÓN

**Estado General:** 🟡 **BUENO CON PROBLEMAS CRÍTICOS DE SEGURIDAD**

El código muestra una arquitectura sólida y bien pensada, con excelente documentación y prácticas científicas rigurosas. Sin embargo, **la exposición de credenciales es un problema crítico que debe resolverse inmediatamente**.

Las deudas técnicas identificadas son manejables y no representan riesgos inmediatos si se abordan en el plazo sugerido. El proyecto está en buen camino, pero necesita atención urgente en seguridad antes de cualquier despliegue público.

**Recomendación:** ✅ **Apto para producción DESPUÉS de resolver problemas críticos de seguridad**

---

**Generado:** 9 de junio de 2026, 21:54 UTC-6  
**Herramienta:** Análisis estático automatizado + Revisión manual
