---
name: Informe semanal
description: "Redacta el informe semanal de progreso a partir de commits, tickets y notas sueltas. Úsala cuando pidan un resumen de la semana, un status report o una actualización para dirección."
agents: [chatgpt, claude, gemini]
tags: [escritura, reporting]
version: 1.0.0
updated: "2026-08-11T10:56:38"
---

# Informe semanal

## Cuándo usarla

Cuando haya que convertir actividad dispersa (commits, tickets, notas de reuniones) en un informe corto que alguien pueda leer en dos minutos.

## Cómo funciona

1. Reúne las fuentes: registro de commits, tickets cerrados y notas de la semana.
2. Agrupa por **resultado**, no por tarea: qué puede hacer ahora el equipo o el producto que antes no podía.
3. Rellena la plantilla de `references/plantilla.md`.
4. Recorta hasta dejarlo en una página. Si algo no cambia una decisión, fuera.

## Reglas de estilo

- Frases cortas y en voz activa.
- Números concretos en lugar de adjetivos: «3 días de retraso», no «bastante retrasado».
- Los riesgos van con su plan de mitigación o no van.
- Nada de relleno: si una semana fue tranquila, el informe es corto.

## Recursos

- `references/plantilla.md` — la estructura fija del informe.
- `references/ejemplo.md` — un informe real ya redactado.
