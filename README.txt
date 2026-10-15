# Competitive Loader 1.1.0

- Interfaz para jugar con el perfil actualizado: reglas competitivas, chat y pausa oficiales del decomp.
- Tiempos online 180, 240, 360 y 480 segundos; sin límite conserva su comportamiento.
- Correcciones del vídeo de apertura y del audio AFS2. El audio no modifica el contador lógico de la sesión online.
- Consulta GitHub antes de jugar e instala automáticamente publicaciones del decomp que superen la validación de compatibilidad. Esta versión admite el ejecutable revisado de v0.1.35.2. Si una publicación futura cambia, conserva la instalación funcional y deja el motivo en el registro; puede requerir un nuevo Loader.
- Registros locales separados por sesión: local.log, online.log, session.json y patch.log; recoge el informe nativo bt3_crash.txt si se genera. Logs con rotación de tamaño. No se suben automáticamente.
- Registra código de salida, versiones y hashes del decomp, payload y memory para investigar cierres, incompatibilidades y desyncs. Un log no identifica por sí solo la causa de toda desincronización.

Extrae el ZIP en una carpeta propia y abre **Competitive Loader.exe**. Para la primera instalación elige tu ISO competitiva y, opcionalmente, tu memory PCSX2. No incluye archivos del juego. Ambos jugadores deben usar las mismas versiones y la misma memory. Mantén el Loader abierto durante el juego para guardar registros y proteger la memory online.

Tab abre el chat oficial. El botón **Abrir registros locales y online** muestra la carpeta de la sesión actual. No hay marcador de sesión propio ni bloqueo propio de la ventana.

Las correcciones y las pruebas de arranque/local no sustituyen la validación online prolongada. La prueba online inicial está descrita en TEST-RESULTS.md; las revisiones de audio y tiempos requieren más partidas reales.
