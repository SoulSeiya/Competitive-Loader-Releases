# Rising Battle — salas BTC (1.4.0, prueba local)

Abre el juego con el Loader de prueba. En **F1 → Rising Battle - Sala BTC** se abre la sala dentro del juego. La entrada online del menú principal del decomp también abre Rising Battle.

## Crear y entrar

El anfitrión escribe su nombre, el nombre de la sala, el puerto TCP (7001 por defecto) y la capacidad (2–32 usuarios). **Crear sala BTC** inicia el servicio en su equipo y genera una clave de invitación. Debe compartir su IP, puerto y clave con los invitados.

Los invitados usan **Unirse a sala**, con su nombre, la IP o nombre de equipo del anfitrión, el puerto y la clave. Para una prueba en el mismo equipo se usa `127.0.0.1`, un Loader distinto por cliente y una sola sala anfitriona en ese puerto. No ejecutes dos juegos sobre la misma carpeta de runtime/memory: usa instalaciones separadas para combatir.

Entre equipos se necesita red local, VPN o acceso al puerto TCP del anfitrión. Esta primera implementación no ofrece servidor público, descubrimiento, relay ni códigos globales de sala. La clave de invitación de la sala es distinta del código de partida del decomp.

## Dentro de la sala

- Lista compartida de usuarios, con identificación del anfitrión y del usuario local.
- Estado **Listo / Esperando**, indicado por cada participante; no inicia un combate automáticamente.
- Chat con los últimos 64 mensajes y anuncios de entradas, salidas y expulsiones.
- El anfitrión puede expulsar a otro usuario; su sesión de sala queda revocada. Puede volver a entrar con una invitación válida: expulsar no es un bloqueo permanente.
- **Salir de sala** abandona la sala. **Cerrar sala**, en el anfitrión, la termina para todos. También termina al cerrar su Loader o perder su conexión durante 30 segundos.

La sala permanece conectada al cerrar su panel y durante las peleas, mientras el Loader siga abierto. **Partida BTC** abre el menú de conexión nativo con FT y las reglas existentes. Los jugadores comparten el código de combate por el chat y se conectan allí. **Volver a la sala Rising Battle** cancela la búsqueda de combate pendiente y regresa al panel. Al regresar de la pelea se puede abrir de nuevo la sala con F1.

Los combates siguen siendo de dos jugadores. La gestión de brackets, inscripciones de personajes, resultados automáticos, relevos y espectadores se añadirá después; no se presenta a quienes esperan como espectadores de una pelea.

## Implementación y diagnóstico

`rising_room.py` sirve el estado y autoriza cada operación en el equipo anfitrión. Cada miembro posee un token aleatorio; solo el anfitrión puede expulsar. Una clave aleatoria permite entrar, se rechazan nombres repetidos y existe límite de usuarios, mensajes y tamaño de peticiones.

`rising_room_bridge.py` mantiene las consultas en un hilo del Loader. `native/competitive_room.cpp` presenta ImGui dentro del juego y se comunica con su Loader mediante memoria compartida de nombre aleatorio por instancia. No realiza conexiones ni esperas de red en el hilo de renderizado. La sala no escribe en el estado de combate ni añade participantes al rollback.

`logs/rising-battle.log` registra creación, entradas, expulsiones, salidas y errores de servicio; no registra tokens, claves ni el texto del chat.

Se ejecutan las pruebas de protocolo y del puente con `python -m unittest discover -s tests -v`. `tests/test_room_ui_native.cpp` es la comprobación adicional con ImGui y SDL3 reales: se compila con los cuatro archivos principales de ImGui del decomp revisado, SDL3 y headers Windows, y recibe el nombre del puente y un puerto de prueba libre. No crea una ventana visible. El objeto distribuido se regenera con `build_score.ps1`.
