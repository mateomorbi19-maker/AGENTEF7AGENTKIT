# Mensajes cortos y ambiguos — nueva revisión de Messenger

Se volvieron a leer seis hilos en Meta Business Suite el 5 de noviembre de 2026. No se enviaron mensajes ni se alteraron etiquetas, asignaciones o automatizaciones. Se omiten nombres y perfiles: interesa el comportamiento conversacional. Las respuestas históricas del negocio no se convierten en reglas comerciales ni fuente de precios.

| Referencia | Mensajes del cliente observados | Comportamiento |
|---|---|---|
| R01 | «Hola» → «Vi unas fundas a medida de Suran» → «Quisiera saber cuanto estan» → «Es el mismo modelo de suran que el del video» | El interés, vehículo y pregunta aparecen separados. Asume que el negocio identifica el video. |
| R02 | «¿Hacen envíos?» → «precio para un Fiat Cronos»; en otras visitas «Dé dónde son» → «Tengo un cronos»; mensaje reciente «precio tengo un cronos» | Pregunta por precio sin completar todos los datos. El hilo tiene visitas separadas por meses: no se concatenan como una única charla continua. |
| R03 | «Hola! 👋 Quiero información ¿Puedo chatear con alguien?» → «Hola, Baic EU5 PLUS» → «Hola, opcion envio» | Apertura de anuncio, modelo aislado y respuesta breve a la pregunta sobre modalidad. |
| R04 | «buen dia» → «para un 207 modelo 2012» | Da vehículo y año sin nombrar el artículo. |
| R05 | «Hola cuánto cuesta para un Fiat Cronos y que dirección es para ir  gracias»; después del video y una pregunta sobre opciones: «Buenísimo y que precio tienen las dos»; después de preguntar por CABA/envío: «Dame el precio de las dos gracias» | Reitera precio en lugar de contestar modalidad. “Las dos” depende del antecedente. No se analizó el video en esta revisión para deducir su orden. |
| R06 | «Hola! 👋 Quiero información ¿Puedo chatear con alguien?» → «Fiat Argo 2018» | Respuesta de solo modelo y año a una apertura automatizada. |

Los casos M03, M05, M11, M12, M27 y M30 del relevamiento del 3 de noviembre aportan además insistencia, cantidad de asientos tardía, repetición del modelo ante una pregunta distinta, «La segunda» / «Pero toda negra» y errores de escritura.

## Cambio en la prueba

El piloto anterior usaba consultas autocontenidas con casi todos los datos y restricciones explícitos. El nuevo ensayo usa tres conversaciones con historial y once turnos: Duster/precio (M03), Suran/video (R01) y Saveiro/configuración tardía (M30). Se conservan los errores de escritura y las omisiones. Los mensajes agrupados en un turno se muestran como burbujas separadas, pero se pasan al modelo unidos por salto de línea: esa agrupación es una decisión de la prueba, no evidencia de los intervalos originales ni validación de Redis.

No se inventan respuestas del agente ni se copian respuestas de la empleada como si fueran del agente. Los resultados de API van en un registro separado. El prompt y los workflows permanecen sin cambios.
