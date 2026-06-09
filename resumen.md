# Resumen del Proyecto: MolDesign IA - Plataforma de Diseño Molecular Científico

Este documento resume el análisis exhaustivo de la estructura, la documentación y los componentes funcionales del proyecto **MolDesign**. El sistema es una plataforma avanzada de *Drug Discovery In Silico* diseñada para superar las limitaciones estadísticas de métodos estándar como AutoDock Vina. Su valor reside en su rigor científico, trazabilidad completa y capacidad de certificación inmutable.

## 🔬 Visión General: ¿Qué es MolDesign?
MolDesign es una herramienta computacional que permite a investigadores diseñar moléculas candidatas contra blancos biológicos específicos (ej. receptores). No es un simple generador de imágenes; es un **sistema científico auditable** que pasa por múltiples filtros de validación antes de emitir un *score* final.

**El Problema Científico Resuelto:**
AutoDock Vina predice bien la *geometría* del encaje (dónde se une), pero su puntuación empírica falla al predecir la *afinidad real* ($\text{Spearman } \rho$ bajo). MolDesign corrige esto mediante un **Rescoring basado en Machine Learning** entrenado sobre el dataset PDBbind 2020.

**El Resultado Final:**
Un **Score Compuesto (0-100)** que pondera:
1.  **Afinidad ML Corregida (45%):** El núcleo del sistema, usando un modelo XGBoost entrenado en interacciones geométricas complejas ($\text{Modelo A} - \text{Modelo NULL}$).
2.  **Propiedades ADME/Drug-likeness (30%):** Filtros fisicoquímicos esenciales (Lipinski, Veber).
3.  **Eficiencia de Ligando (LE) y Rigor Estructural (SA Score) (25%):** Métricas que penalizan moléculas grandes o químicamente inestables.

---

## 🏗️ Arquitectura del Sistema: Un Enfoque Modular y Distribuido
El sistema está diseñado como una arquitectura de microservicios, orquestada por Docker Compose para garantizar la separación estricta de responsabilidades (Principio Rector).

### Componentes Clave:
1.  **Frontend (`frontend/`):** Construido con Next.js 14. Es la interfaz de usuario que guía al científico a través del proceso y muestra los resultados interpretados.
2.  **API Gateway (`backend/api/`):** Un servicio FastAPI (Python) que actúa como el punto de entrada único. Recibe las peticiones, valida parámetros y encola tareas pesadas en Redis.
3.  **Worker Celery (`backend/worker`):** El motor de ejecución asíncrona. Consume tareas de docking o rescoring y gestiona la comunicación con los servicios especializados.
4.  **Rescoring Service (`rescoring/`):** **El corazón científico.** Es un microservicio dedicado (Python 3.12) que ejecuta el modelo ML avanzado, utilizando librerías especializadas como ODDT y XGBoost para calcular el *score* final.
5.  **Almacenamiento:** Utiliza MinIO (S3-compatible) para almacenar artefactos binarios (PDBQT, SDF).
6.  **Trazabilidad:** La certificación de resultados se realiza en la blockchain de **Solana Devnet**, proporcionando una prueba inmutable del descubrimiento.

---

## ⚙️ Flujo de Trabajo Paso a Paso (Pipeline E2E)
El proceso es lineal y altamente controlado:

1.  **Input Molecular:** El usuario ingresa un SMILES $\rightarrow$ Se valida la química básica (RDKit).
2.  **Generación 3D:** Se genera una conformación bioactiva (ETKDG v3).
3.  **Docking Inicial:** AutoDock Vina calcula las poses iniciales y puntuaciones empíricas.
4.  **Filtrado de Pose:** Se aplican filtros geométricos rigurosos (contacto, enterramiento) para descartar resultados físicamente imposibles.
5.  **Rescoring ML:** El servicio `rescoring/` toma las poses filtradas y aplica el modelo XGBoost ($\text{Modelo A} - \text{Modelo NULL}$) para obtener una afinidad corregida.
6.  **Scoring Compuesto:** Se calcula el Score final (0-100) ponderando la afinidad, ADME y Drug-likeness.
7.  **Output Científico:** El sistema genera un reporte detallado que incluye:
    *   El score compuesto.
    *   La fuente de cada componente del score.
    *   Un *hash* SHA-256 asociado a la transacción en Solana, certificando el hallazgo.

---

## 📜 Principios Rectores y Ética (Guía para Contribuidores)
Los archivos `CONTRIBUTING.md` y `readme.md` establecen reglas estrictas que deben guiar cualquier desarrollo futuro:

*   **Validez Científica > UX:** Cualquier mejora de usabilidad nunca debe comprometer la validez científica o la trazabilidad.
*   **No Alucinación:** La IA solo puede *interpretar*, no calcular ni afirmar resultados sin fuente.
*   **Trazabilidad Obligatoria:** Cada número, cada parámetro (ej. `seed=42`, versión de Vina) debe ser rastreable para garantizar la reproducibilidad total del experimento.

---

## ✅ Conclusión y Verificación
El proyecto es una plataforma de investigación de vanguardia que combina química computacional clásica con Machine Learning avanzado y tecnología *blockchain*.

**Para verificar el funcionamiento:**
1.  **Despliegue:** Se debe ejecutar `docker compose up --build -d` (asumiendo que los servicios externos como Postgres/Redis están disponibles).
2.  **Flujo de Prueba:** El usuario debería interactuar con la interfaz del **Frontend (Puerto 3001)**, lo cual disparará el flujo completo: API $\rightarrow$ Worker $\rightarrow$ Rescoring Service $\rightarrow$ Resultado en UI.