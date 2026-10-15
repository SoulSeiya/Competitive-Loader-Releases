# Competitive Loader 1.2.0

- La ventana bloquea arrastre, redimensionado, menú de sistema y F11 durante el online. Al terminar la sesión recupera su comportamiento normal; cerrar el juego sigue disponible.
- Aviso con las mejoras de la versión al abrirla por primera vez, también después de actualizar. El registro del Loader muestra las notas de GitHub al iniciar una actualización.
- Corrección de la inicialización en cero de los parches nativos.
- Marcador online permanente con nombres y victorias de cada jugador. Se conserva durante selección de personajes, peleas y revanchas; se reinicia al terminar la sesión.
- Los resultados esperan la confirmación de los inputs nativos. Los fotogramas repetidos por rollback no duplican victorias. Los empates se muestran aparte y los abortos no suman.
- Cada cambio confirmado queda en online.log como `net: score confirmed`, con tick y totales P1/P2/empates.
- Interfaz para jugar con el perfil actualizado: reglas competitivas, chat y pausa oficiales del decomp.
- Tiempos online 180, 240, 360 y 480 segundos; sin límite conserva su comportamiento.
- Correcciones del vídeo de apertura y del audio AFS2. El audio no modifica el contador lógico de la sesión online.
- Consulta GitHub antes de jugar e instala automáticamente publicaciones del decomp que superen la validación de compatibilidad. Esta versión admite el ejecutable revisado de v0.1.35.2. Si una publicación futura cambia, conserva la instalación funcional y deja el motivo en el registro; puede requerir un nuevo Loader.
- Registros locales separados por sesión: local.log, online.log, session.json y patch.log; recoge el informe nativo bt3_crash.txt si se genera. Logs con rotación de tamaño. No se suben automáticamente.
- Registra código de salida, versiones y hashes del decomp, payload y memory para investigar cierres, incompatibilidades y desyncs. Un log no identifica por sí solo la causa de toda desincronización.

Extrae el ZIP en una carpeta propia y abre **Competitive Loader.exe**. Para la primera instalación elige tu ISO competitiva y, opcionalmente, tu memory PCSX2. No incluye archivos del juego. Ambos jugadores deben usar las mismas versiones y la misma memory. Mantén el Loader abierto durante el juego para guardar registros y proteger la memory online.

Tab abre el chat oficial. El botón **Abrir registros locales y online** muestra la carpeta de la sesión actual. El marcador se muestra arriba durante toda la sesión online. Durante el online la ventana queda protegida frente a movimiento y cambios de tamaño.

Las correcciones y las pruebas de arranque/local no sustituyen la validación online prolongada. La prueba online inicial está descrita en TEST-RESULTS.md; las revisiones de audio y tiempos requieren más partidas reales.
