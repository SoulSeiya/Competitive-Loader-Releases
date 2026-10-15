# Primera prueba local — 2026-10-15

Resultado: **sin divergencias observadas en esta prueba**, no certificación de estabilidad.

Dos instancias reales del ejecutable Windows revisado de decomp 0.1.35.2, en carpetas independientes, con la ISO competitiva 8.4.2 y la misma partida importada. Se compararon por hash los 68.617 archivos de cada runtime considerados por el preflight (datos de juego, partidas, ejecutable y .dat) antes de conectar.

Perfil experimental: 17 entradas competitivas, 65 ramas directas adaptadas, cero wrappers antiguos y cero cambios de etiquetas de tiempo. No se cargó competitive_chat.o. Tiempos oficiales, pausa/chat/red oficiales; sin conversión de intro.

- Conexión directa 127.0.0.1, rollback 8, delay 2; sin pérdida ni latencia artificial.
- Entrada reproducible generada por tools/make_online_script.py.
- Duración programada: 90 segundos por instancia.
- Arranque online terminado en blank 1073 en ambos lados.
- Misma huella de datos de gameplay: 0f6de7e0.
- 5.569 blanks comunes analizados; 3.053 de combate.
- Sin diferencias observadas en vida, posiciones y reloj de los blanks de combate comparados.
- Vida inicial 40.000 en ambos; mínimos observados 35.320 y 35.180. Hubo movimiento y daño, no solo menús o espera.
- No apareció el mensaje nativo de desync ni un informe bt3_crash.txt.

El cierre programado dejó una línea final de hashes incompleta. Se corrigió el analizador para ignorar ese registro; se repitió el análisis de los mismos archivos y se añadió cobertura a la prueba de regresión.

Pruebas Python: 9 correctas, 1 omitida por no tener el ejecutable del Loader construido en la copia de desarrollo. La prueba omitida verifica el paquete del actualizador, no la simulación.

## Límites

No se comparó aún este recorrido contra el Loader antiguo. No demuestra que se haya identificado la causa de los reportes existentes. Faltan red con lag/pérdida, revancha, clashes, transformaciones, sesiones largas y dos equipos distintos. El perfil sigue usando los objetos de gameplay anteriores; la regeneración reproducible del payload y su revisión contra estructuras actuales quedan pendientes.

La GUI conserva el parche anterior. Este experimento solo se activa mediante local_online_test.py; no se creó ni reemplazó una Release.
