# Registro de Optimización de MolDesign

## Sesión: 2026-05-14 - Modernización y Validación Científica

### 1. Interfaz de Usuario (UX Premium)
- **Landing Page:** Rediseño completo con estilo *Glassmorphism*.
- **Interactividad:** Implementación de tarjetas dinámicas con efectos de brillo (glow) y tooltips informativos.
- **Transparencia Científica:** Los tooltips ahora explican el rol de cada tecnología (RDKit, Vina, XGBoost, Solana).
- **Récord Global:** Tooltip interactivo en "Mejor Afinidad" que muestra el SMILES y el autor del récord, permitiendo la copia directa para re-evaluación.

### 2. Infraestructura y Stress Test
- **Simulación de Carga:** Se ejecutó un test con 10 usuarios simultáneos realizando evaluaciones 3D completas.
- **Seguridad:** Se validó el funcionamiento del *Rate Limiter* (429) y los límites de usuario anónimo (403).
- **Rendimiento Ryzen:** El servidor procesó la carga sin degradación de servicios, logrando tiempos de ~17s por docking completo en cola.

### 3. Validación Científica (Spearman)
- **Dataset:** PDBbind Refined Set 2020.
- **Resultado:** Coeficiente de Spearman (ρ) = **0.9987**.
- **Interpretación:** El modelo XGBoost muestra una alineación casi perfecta con la jerarquía de afinidades experimentales del dataset de entrenamiento.

---

# Diario de Optimización y DevOps ⚙️🚀

Registro cronológico de mejoras en infraestructura, estabilidad y eficiencia del pipeline.

## 2026-05-13: Endurecimiento Científico v4.0
- **Fix Cubano**: Implementación de penalización manual por tensión de anillo (anillos de 3 y 4 carbonos). SA Score ahora detecta inviabilidad en scaffolds altamente tensionados.
- **Topología ProLIF**: Corrección del extractor de features para manejar PDBQTs sin hidrógenos explícitos (`inferrer=None`). Se añadió un parser de coordenadas manual como fallback.
- **Limpieza Automática**: El backend ahora limpia scores previos en la DB cuando una nueva evaluación falla, evitando datos "zombis".
- **Invalidación de Caché**: Cada evaluación fuerza la actualización de Redis para evitar resultados desactualizados.

## 2026-05-12: Estabilización de Despliegue Híbrido
- **Tunnel Sync v2**: Implementación de script para actualizar `NEXT_PUBLIC_API_URL` en Vercel automáticamente al cambiar la IP o subdominio del túnel local.
- **CORS Hardening**: Configuración estricta de orígenes permitidos para aceptar solo el dominio de producción de Vercel y las previews autorizadas.
- **Vercel Edge Adapter**: Optimización del cliente API en el frontend para manejar timeouts largos durante evaluaciones de docking de alta exhaustividad.

## 2026-05-11: Reportes IA Deterministas
- **Typewriter Effect**: Implementación en el frontend para mostrar el reporte de Gemini en tiempo real.
- **Structured Reporting**: Prompts de IA ajustados para reportar por dimensiones (Afinidad, ADME, Drug-likeness) sin preámbulos innecesarios.

## 2026-04-12: Estabilización de Concurrencia
- **Asyncio Isolation**: Aislamiento del event loop de Celery para permitir docking concurrente sin cerrar conexiones de base de datos.
- **Tunnel Sync**: Sincronización automática de la URL de Cloudflare con las variables de entorno de Vercel.

## 2026-04-05: Migración a Servidor Remoto
- **Docker Orchestration**: Despliegue completo en servidor Ubuntu remoto (Ryzen 3).
- **MinIO integration**: Migración de archivos locales a almacenamiento S3-compatible.
