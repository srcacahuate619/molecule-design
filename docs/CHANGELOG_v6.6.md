# Changelog v6.6 (Microservices & Scalability)

## Nuevas Características y Mejoras
- **Arquitectura de Microservicios:** Se migró el monolito a tres contenedores separados: `frontend` (Next.js), `api` (FastAPI Core + Celery Worker) y `rescoring` (FastAPI dedicado a ML).
- **Cola de Tareas Asíncrona:** Implementación de Celery + Redis para manejar evaluaciones de docking pesadas en segundo plano, evitando timeouts en el frontend y permitiendo escalado horizontal de workers.
- **Enrutador Físico Adaptativo (GNN):** Integración completa del modelo de Red Neuronal de Grafos (RTMScore) en el microservicio de rescoring.
- **Parseador 3D Robusto:** Inclusión de `Meeko` como parseador principal de PDBQT para solucionar fallos de lectura de coordenadas 3D en MDAnalysis.
- **Desglose de Farmacóforos UI:** Nueva UI interactiva tipo Radar Chart para desglosar la atención de la GNN por tipo de farmacóforo (Aromáticos, Donadores, Aceptores, etc.).

## Optimizaciones
- Reducción masiva en el uso de memoria RAM del servidor web al delegar la carga de modelos PyTorch/DGL al contenedor aislado de `rescoring`.
- Comunicación RESTful entre microservicios con manejo de errores robusto.

## Errores Conocidos (Known Bugs)
- **Desglose Farmacóforos "No disponible":** En ciertas moléculas (como el Paracetamol), el algoritmo de isomorfismo de grafos falla al intentar mapear los átomos pesados provenientes de Meeko/Vina contra la representación perfecta 2D del SMILES. Esto causa que el sistema asuma que no hubo correspondencia de atención y oculte el gráfico de radar. *Resolución pendiente*.
