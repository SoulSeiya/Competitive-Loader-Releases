Competitive Loader 1.5.4 — candidato en validación.

Dragon Net Battle conserva Partidas y Torneos BTC. F2 muestra el bracket y Tab
abre el chat de sala. El menú normal no incluye bots de prueba, simuladores ni
accesos al laboratorio. La prueba de espectador se distribuye por separado.

Matchmaking de peleas: https://btc-matchmaking.paulogomez41.workers.dev
El alojamiento permanente de salas de torneo y el espectador online en directo
siguen pendientes. Ambos jugadores necesitan los mismos datos y memory compatibles.
Guía de uso: RISING-BATTLE.md. Registros: carpeta logs junto al Loader.

## Funciones conservadas

- Corrige el descriptor de los modelos embebidos de efectos: el tamaño fijo 32 que usa el decomp ya no se confunde con la longitud del archivo. Se recupera un límite dentro de la asignación activa de memoria antes de llamar al constructor original. La traza reportada del ataque 1 de Androide 16 fallaba en esta ruta al quedar vacío el puntero del modelo. El usuario repitió el ataque con esta versión y confirmó que funcionó sin el cierre reportado.
- **FT1 a FT5** en F1 → Online → Host → Primero a (FT). El anfitrión lo elige antes de conectar y ambos reciben el mismo objetivo. Sin FT conserva las partidas libres. La búsqueda rápida no usa este FT privado.
- El primero en alcanzar las victorias elegidas gana el set. Los empates no suman victorias. El marcador se congela, muestra **GG y el ganador en grande** durante unos segundos y termina la sesión online de ambos mediante la salida nativa.
- La selección de personajes muestra el nombre del rival conectado.
- Botón **Buscar actualizaciones** en el Loader: vuelve a consultar GitHub sin reiniciar. Instalar una actualización sigue reiniciando únicamente el Loader.
- Para compartir el FT, ambos jugadores deben usar la misma versión del Loader con las mismas reglas y datos.
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
