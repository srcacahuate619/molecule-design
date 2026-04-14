# Directorio de artefactos del microservicio de rescoring
# Los modelos entrenados se generan en Fase 2 y se colocan aquí.
# En Fase 1, este directorio está vacío y el servicio arranca en modo degradado.
#
# Artefactos esperados (post-Fase 2):
#   model_a.joblib                - Modelo A (XGBoost rank:pairwise, features completas)
#   model_null.joblib             - Modelo NULL (XGBoost rank:pairwise, solo 1D/2D)
#   delta_distribution.json       - Distribución de Delta para umbrales de semáforo
#   applicability_domain.json     - Media, cov_inv y umbral de Mahalanobis
#   training_report.json          - Métricas, versión, fecha, feature order
#   frozen_test_set.json          - Test set congelado (~500 complejos)
#   pdbbind_audit_report.json     - Auditoría del dataset "Solo Casos VIP"
