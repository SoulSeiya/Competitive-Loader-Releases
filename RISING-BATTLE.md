# Rising Battle 1.5.0 — prueba de cuatro

## Iniciar la prueba

La entrada **Tenkaichi Budokai Online** del menú principal abre ahora Rising Battle en pantalla completa. Dragon Net Battle conserva su ventana, Host/Join, FT y códigos. Se adapta únicamente la entrada del modo PC TBO del ejecutable revisado; no se desactiva globalmente la comprobación de datos originales.

Para la prueba preparada, abre **Prueba torneo de 4.bat** junto al Loader. Usa un runtime humano aislado, con una copia de tu save competitivo. Entra por **Tenkaichi Budokai Online** y pulsa **Crear prueba: tu + 3 bots, todos contra mi**. Se inscriben cuatro participantes y se propone FT1. Puedes cambiar nombre y FT, guardar las reglas y pulsar **Iniciar prueba**.

La modalidad de laboratorio **Todos contra mí** programa tres sets consecutivos, uno contra cada bot. El humano sigue jugando aunque pierda y conserva P1 y el control de los menús. No tiene campeón ni elimina participantes; sirve para probar FT, retorno a sala y cambio de rival. El torneo normal conserva el bracket de eliminación directa con sorteo y pases libres. En cada cruce se conectan solo dos jugadores por el matchmaking nativo. Los bots confirman selecciones y usan entradas programadas de movimiento, golpes y ki. No son IA avanzada ni modifican el daño del juego.

## Observar mientras esperas

**Ver combate local de bots (otra ventana)** muestra una instancia propia del bot en este equipo cuando el anfitrión espera en la sala. La prueba Todos contra mí te mantiene como jugador en todos los cruces y no cubre esa espera. Esta función es una vista local de laboratorio, no una tercera conexión de espectador online. El espectador por reproducción de entradas/replay todavía no está implementado.

## Torneo y reglas

El anfitrión configura nombre/temática, FT1–FT5 y máximo de 1–5 personajes por jugador. Cada usuario se inscribe indicando sus personajes separados por comas. La lista se guarda y se valida en la inscripción, pero todavía no restringe la selección real dentro del combate. Cambiar el límite de personajes reinicia las inscripciones.

Iniciar torneo cierra las inscripciones y genera un bracket de eliminación directa. El chat anuncia pases, cruces, ganadores y campeón. Cada set avanza al recibir el mismo marcador válido de ambos jugadores; las entregas repetidas son idempotentes. Un resultado contradictorio detiene el avance hasta que los jugadores coincidan o el anfitrión resuelva una baja por WO. Un miembro que sale o es expulsado pierde sus participaciones pendientes por WO. El anfitrión puede cancelar el torneo y abrir nuevas inscripciones.

Los bots de sala normales siguen disponibles para simular brackets sin ejecutar combates. **Simular siguiente cruce** se limita a cruces entre dos bots de sala. Los bots de combate se resuelven jugando, no mediante ese botón.

## Procesos, memoria y registros

Solo se abren instancias de bots cuando les toca. Cada bot dispone de archivos del runtime y saves propios; sus datos del juego se leen desde la instalación competitiva. Cada worker mantiene su protección de memory en un proceso Python/Loader separado, sin sustituir los handles del usuario. Los auxiliares se asignan a jobs de Windows propios antes de lanzar juegos; cerrar esos jobs no termina juegos ajenos.

Las instancias que acaban un cruce conservan un margen para completar GG/salida nativa antes de retirarse. Un bot que vuelve en otra ronda recibe un workspace nuevo. El anfitrión conserva el control de la sala. Cerrar la sala o el Loader detiene los auxiliares de esa prueba. Los logs, hashes y metadatos de procesos propios quedan en **logs/tournament-lab**; no se suben automáticamente. Esa carpeta puede contener copias de runtime y memory, y está excluida de Git.

## Red y trabajo pendiente

La sala local sigue usando IP/puerto o invitación BTC1, que incorpora dirección, puerto y clave. No es el servicio público de códigos cortos solicitado. En la prueba la sala está en loopback y solo participa este equipo; las peleas usan el matchmaking nativo existente.

El servicio público BTC con código corto, la validación de personajes seleccionados y el espectador online por replay siguen pendientes. No hay cuenta Cloudflare, despliegue ni endpoint público de salas BTC. Workers/Durable Objects es la arquitectura propuesta; workers.dev evita necesitar dominio propio para empezar. No se han probado todavía torneos completos entre varios equipos.

## Desarrollo

rising_tournament.py implementa bracket, circuito de prueba, inscripciones, resultados y bajas; rising_room.py autoriza el protocolo. rising_room_bots.py mantiene miembros de prueba; rising_game_bots.py administra sus procesos reales. El puente ABI 4 comunica estado con ImGui sin hacer red en el hilo de renderizado.

build_score.ps1 regenera el objeto nativo. tests/test_room_ui_native.cpp comprueba frames ImGui, la entrada TBO, Dragon Net Battle, pads de bot, roles, handoff de código y resultados FT mediante dobles del motor. Las pruebas Python cubren el motor, HTTP, puentes y aislamiento de jobs. --smoke-room valida los módulos empaquetados solo en loopback.
