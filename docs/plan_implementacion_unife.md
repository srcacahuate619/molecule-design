# Plan de Implementación: Transformación de MolDesign a SaaS de Código Abierto (Caso UNIFÉ)

Este plan describe la hoja de ruta estratégica y técnica para adaptar MolDesign de su estado actual (MVP monousuario) a una plataforma SaaS comercializable en el sector académico, tomando como piloto a la **UNIFÉ (Universidad Femenina del Sagrado Corazón)** en Perú.

---

## 🎯 Objetivo General
Transformar MolDesign en un SaaS multi-inquilino (*multi-tenant*) y de código abierto (*open-core*), enfocado didáctica y científicamente en **bioinformática de fitonutrientes y nutracéuticos** para la Facultad de Nutrición, y en **innovación tecnológica (IA + Blockchain)** para la Facultad de Ingeniería de Sistemas.

---

## 📋 Fases del Plan

### Fase 1: Alineación Científica y Comercial (UNIFÉ)
- **Objetivo:** Adaptar el producto visual y narrativamente para la propuesta piloto de Nutracéuticos.
- **Acciones:**
  - Crear una biblioteca preestablecida de dianas metabólicas de nutrición (SIRT1, COX-2, AMPK, PPARγ) contemplando estados conformacionales específicos (Activo vs Inactivo/Inhibido).
  - Diseñar una librería de 20 fitonutrientes peruanos clave (resveratrol, curcumina, quercetina, antocianinas, etc.) cargada por defecto en la base de datos para demostraciones.
  - Generar el dossier comercial en Markdown/PDF basado en la vinculación FAO AGRIS y la diferenciación de estados conformacionales.

### Fase 2: Re-arquitectura Técnica (SaaS Ready)
- **Objetivo:** Modificar el backend y la base de datos para soportar múltiples usuarios concurrentes y aislamiento de datos.
- **Acciones:**
  - **Base de Datos (PostgreSQL):** 
    - Modificar esquemas para añadir `organization_id` y `user_id` con borrado en cascada.
    - Adaptar la tabla de targets para admitir múltiples PDBs por diana biológica según su estado conformacional (Activo vs Inactivo).
  - **UI/Frontend:** Implementar un selector/toggle en la interfaz Modo Pro para alternar entre conformaciones (Activo/Inactivo) de las dianas (GLP-1R, ER-α, AKT1, SIRT1).
  - **Control de Colas (Celery/Redis):** Configurar dos colas asíncronas separadas:
    - `cola_premium` (para profesores/investigadores con workers dedicados).
    - `cola_free` (para alumnos en Modo Gamer con límites estrictos de procesamiento).
  - **Seguridad (Autenticación):** Integrar OAuth2/SSO para el correo institucional de la universidad (Google Workspace / Azure AD).

### Fase 3: Integración de la Licencia Open-Source y Monetización
- **Objetivo:** Definir las reglas de distribución del código y la integración de Stripe.
- **Acciones:**
  - Configurar la licencia **AGPLv3** para el core del repositorio.
  - Añadir soporte para suscripciones universitarias basadas en créditos de simulación/cómputo.

---

## 📝 Preguntas Abiertas para el Usuario (Feedback Requerido)

> [!IMPORTANT]
> Por favor, revisa y responde a los siguientes puntos para ajustar los alcances:
> 
> 1. **¿El piloto debe correr en tu servidor local?** 
>    Dado que usas un túnel dinámico (Cloudflared/Ngrok) hacia tu servidor Ryzen 3 local, ¿el piloto inicial para la UNIFÉ usará tu servidor físico como backend central, o quieres que el plan contemple la migración completa de los Celery Workers a servidores con GPU en la nube (ej. AWS EC2 o RunPod)?
> 
> 2. **¿Añadimos la biblioteca peruana de fitonutrientes directamente a la UI del Modo Gamer?**
>    ¿Te gustaría que los estudiantes puedan seleccionar ingredientes nativos (ej. "Maca", "Camu Camu", "Maíz Morado") desde un menú desplegable en el frontend en lugar de tener que buscar o dibujar la molécula química en Ketcher? Esto facilitaría enormemente las clases de pregrado.

---

## 🔬 Plan de Verificación

### Pruebas de Software:
*   **Prueba de Aislamiento:** Validar que un usuario de la organización A no pueda ver los resultados de docking de la organización B.
*   **Prueba de Fair-Share (Celery):** Lanzar 100 tareas pesadas del Modo Gamer (alumnos) y verificar que una tarea del Modo Pro (profesor/investigador) se procese inmediatamente a través de la cola premium sin quedarse encolada.

### Pruebas de Negocio:
*   Presentar el dossier comercial estructurado en `propuesta_unife.md` al intermediario para validar si el lenguaje es idóneo antes de la reunión con la decana de Nutrición.
