# CONTEXTO_ASISTENTE.md
> Archivo canónico del proyecto. Actualizar al final de cada sesión de trabajo.
> Si estás leyendo esto en una conversación nueva: lee TODO este archivo antes de responder cualquier cosa.

## ¿Qué es este proyecto?

**Nombre:** App de Cotizaciones con IVA
**Organización:** Grupo Jenta — Pasto, Colombia
**Desarrollador principal:** Gustavo (Grupo Jenta)
**Repositorio:** (pendiente de crear — nombrar `cotizaciones-iva-api` para el backend y `cotizaciones-iva-app` para la app móvil)

### Problema que resuelve
Gustavo es vendedor. Su ERP permite generar cotizaciones para clientes e imprimirlas como PDF. El problema: ese PDF no incluye los precios con IVA, solo los precios base. Los clientes se quejan porque no pueden ver el precio final.

### Solución
Una app móvil que:
1. Recibe el PDF de cotización exportado del ERP
2. Lo analiza, detecta los precios sin IVA
3. Calcula el precio con IVA (19% en Colombia, configurable)
4. Regenera el mismo PDF con diseño idéntico al original pero con los precios con IVA incluidos
5. Entrega el PDF listo para compartir/imprimir al cliente

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Procesamiento PDF | Python + pdfplumber + PyMuPDF + reportlab |
| API REST | FastAPI + Uvicorn |
| App móvil | React Native + Expo SDK |
| Deploy backend | Railway |
| Build app | EAS (Expo Application Services) |

**IVA Colombia:** 19% (default configurable)

## Estado actual de fases

- Fase 0 — Diagnóstico del PDF: ✅ COMPLETADO (24/06/2026)
- Fase 1 — Motor Python: ⬜ PENDIENTE
- Fase 2 — API REST FastAPI: ⬜ PENDIENTE
- Fase 3 — App React Native: ⬜ PENDIENTE
- Fase 4 — Pulido y producción: ⬜ PENDIENTE

## Resultados Fase 0 — Diagnóstico de PDF
- **Fecha:** 24/06/2026
- **Texto seleccionable:** Sí
- **Precios detectados:** 11 (en formato pesos colombiano: $1.500.000,00)
- **Patrón numérico dominante:** pesos_colombiano (punto como separador de miles, coma como decimal, prefijo $ opcional)
- **Conclusión:** LISTO PARA FASE 1 — no requiere OCR

## URL Backend Producción
(pendiente — completar después de Fase 2)

## Decisiones técnicas tomadas
- Estrategia de edición PDF: superposición controlada con PyMuPDF (cubre precio original con rect blanco, escribe nuevo valor encima)
- IVA configurable desde la app (no hardcodeado)
- Deploy Railway (detecta Python desde requirements.txt)
- Build APK directo con eas build --profile preview (sin Play Store)

## Cómo continuar en una sesión nueva con Claude
1. Pega este archivo completo al inicio del chat
2. Indica la fase actual y qué tareas ya se completaron (cambiar ⬜ por ✅)
3. Describe el problema o tarea siguiente
4. Claude generará el prompt para continuar

*Última actualización: 24/06/2026 — Fase 0 completada, proyecto listo para Fase 1.*
