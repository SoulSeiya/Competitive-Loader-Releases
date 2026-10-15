# Rising Battle 1.5.1 — Dragon Net Battle, salas y torneos

## Entrar y probar

Abre el Loader 1.5.1. En **F1 → Online → Dragon Net Battle** verás **Partidas** y **Torneos BTC**. Partidas conserva Host, Quick match y Join con sus códigos nativos, reglas y FT. La entrada Tenkaichi Budokai Online también abre Torneos BTC como acceso alternativo.

En Torneos BTC, pulsa **Crear prueba: tú + 3 bots, todos contra mí**. Se crean cuatro inscritos y una sala del servicio local con código BTC de seis caracteres. Se propone FT1; puedes cambiar nombre y FT, guardar e iniciar la prueba. Jugarás tres sets consecutivos, uno contra cada bot, incluso si pierdes. Tú conservas P1 y el control de menús. Los bots confirman y usan entradas programadas de movimiento, golpes y ki; no son IA avanzada ni cambian el daño.

La prueba Todos contra mí es un circuito de laboratorio, sin eliminaciones ni campeón. El torneo normal conserva el sorteo, bracket de 2–32 inscritos y pases libres. El chat anuncia cruces, resultados y campeón. Cada set avanza cuando ambos jugadores entregan el mismo marcador válido. Los resultados repetidos no cuentan dos veces; los contradictorios requieren revisión o WO del anfitrión.

## F2 y Tab

**F2** muestra u oculta el bracket actualizado de la sala, también durante el combate. Es una vista de consulta: no pausa ni toma el teclado del juego. En Todos contra mí muestra los tres sets y sus estados.

**Tab** reutiliza el chat nativo del juego y lo conecta a todos los miembros de la sala. No hay un segundo chat dentro del panel de torneo. Enter envía; Esc/Tab cierra. Desde la pestaña de torneo, Tab cierra el panel y abre el chat. La inscripción, las reglas y los anuncios siguen sincronizados durante las peleas. Fuera de una sala BTC, el chat conserva su funcionamiento nativo entre los dos jugadores.

## Room codes de sala

El servicio BTC propio mantiene varias personas conectadas bajo **BTC-XXXXXX**. Para varios Loaders de este equipo, pulsa **Iniciar servicio local de prueba** en uno, usa su URL local en todos, crea una sala y comparte su código. La prueba automática de bots puede iniciar un servicio en un puerto libre; su URL aparece junto al código. Cerrar el Loader que aloja ese servicio local lo termina.

Los códigos nativos de Dragon Net Battle siguen enlazando exclusivamente a los dos jugadores de cada combate. El código BTC pertenece a la sala completa y no se consume al empezar una pelea. La conexión directa avanzada por IP/VPN e invitación BTC1 continúa disponible.

El coordinador está implementado y probado localmente, pero **todavía no está alojado en Internet**. Para usarlo entre equipos sin exponer puertos de sala, hay que desplegarlo con HTTPS y configurar la misma URL en los clientes. No hay cuenta ni endpoint público configurados. Véase service/README.md. No se distribuye ni retransmite contenido del juego.

## Límites y registros

El anfitrión configura temática, FT1–FT5 y de 1–5 personajes declarados. La inscripción valida nombres y cantidades, pero aún no restringe los personajes elegidos dentro del combate. Cambiar ese límite reinicia las inscripciones. El anfitrión puede expulsar, resolver WO y cancelar el torneo. Salir o perder conexión provoca WO; salir el anfitrión cierra la sala.

**Ver combate local de bots** permite mostrar otra instancia propia cuando el anfitrión espera. Todos contra mí te mantiene jugando y no cubre esa espera. El espectador online por replay aún no está implementado.

Cada bot usa runtime, save y proceso propios; solo arranca cuando le toca. Se retiran exclusivamente sus procesos mediante jobs de Windows. El humano usa una copia aislada del save en el candidato preparado. Los datos se leen de la instalación competitiva. Los registros y hashes quedan en logs/tournament-lab, excluidos de Git; no se suben automáticamente.

El servicio guarda estado en memoria: reiniciarlo elimina sus salas. Hay pruebas de protocolo, cuatro clientes, autorizaciones y torneo completo; no se ha probado todavía entre equipos por Internet ni bajo carga pública. El puente entre Loader y juego usa ABI 5; la red se realiza fuera del hilo de renderizado.
