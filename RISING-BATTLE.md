# Rising Battle 1.4.1 — desarrollo

Dragon Net Battle conserva su entrada, ventana y códigos originales. La ruta normal vuelve al menú nativo; el panel provisional se abre solo desde **F1 → Pruebas de sala BTC (desarrollo)**. La versión de prueba 1.4.0 sustituyó ese menú por una interpretación incorrecta de la petición.

El modo que se debe adaptar es **Tenkaichi Budokai Online**, implementado en src/menu/port_tbo.c del decomp. Tb_Vanilla comprueba los datos originales del disco y bloquea ediciones modificadas. Su adaptación a los torneos BTC sigue pendiente. No se ha desactivado globalmente esa validación.

## Probar bots y salas

Crea una sala con nombre, capacidad 2–32 y puerto TCP (7001 por defecto). El anfitrión dispone de **Añadir 1 bot de prueba**, **Llenar con bots** y **Retirar bots**. Los bots usan sesiones HTTP reales, aparecen como BOT, escriben un mensaje y alternan listo/esperando. Pueden expulsarse y no se reconectan solos. No controlan personajes ni simulan latencia externa.

La sala conserva lista, chat, listo y expulsiones del anfitrión. Solo el anfitrión puede añadir bots. Cerrar su sala o el Loader la termina; los miembros caducan sin latido. Expulsar revoca la sesión actual, sin bloquear permanentemente una nueva entrada con invitación válida.

**Abrir Dragon Net Battle** vuelve al menú de combate nativo, sin renombrarlo ni añadir controles a su ventana. La sala sigue conectada mientras el Loader permanezca abierto. Para volver al panel provisional se usa su entrada explícita de F1.

## Invitación provisional BTC1

Revisa **IP / equipo para la invitación** con la dirección local, VPN o un nombre accesible. **Copiar código de sala** copia una invitación que se pega en **Unirse a sala → Entrar con código**. También existe la entrada por IP/puerto/clave.

BTC1 incorpora dirección, puerto y clave, con comprobación de errores de escritura. No publica una sala en Internet, no atraviesa NAT y no es el código corto solicitado. 127.0.0.1 sirve únicamente en el mismo equipo. Entre equipos todavía hace falta red local, VPN o puerto TCP accesible. Para probar combates locales se usan runtimes y memories separados.

## Servicio público previsto

El objetivo es crear sala → recibir código corto → pegarlo en Join. Un servicio central BTC guardará miembros, permisos del anfitrión, chat y posteriormente el torneo. Cloudflare Workers con Durable Objects permite organizarlo; una dirección workers.dev evita necesitar dominio propio. Todavía no hay cuenta, servicio desplegado ni endpoint público configurado.

Las salas y el tráfico de las peleas son funciones distintas. Publicar un servicio HTTP por un túnel no sustituye automáticamente el transporte UDP del netplay. No se utiliza el matchmaking público del decomp como si admitiera salas de más de dos jugadores.

Referencias oficiales:
- https://developers.cloudflare.com/workers/configuration/routing/workers-dev/
- https://developers.cloudflare.com/durable-objects/best-practices/websockets/
- https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/protocols/

## Desarrollo

rising_room.py autoriza las operaciones. rising_room_bots.py ejecuta clientes de prueba. rising_invite.py codifica invitaciones. rising_room_bridge.py mantiene la red fuera del hilo de renderizado y comunica ImGui con su Loader mediante memoria compartida por instancia. No añade jugadores al rollback ni escribe el estado de combate.

logs/rising-battle.log registra operaciones y errores sin tokens, claves ni texto del chat. Ejecuta python -m unittest discover -s tests -v. build_score.ps1 regenera el objeto nativo. tests/test_room_ui_native.cpp comprueba ImGui, SDL, Windows, la ruta original de Dragon Net Battle y los comandos del puente. --smoke-room comprueba servicio, bots e invitaciones desde el EXE congelado solo en loopback.
