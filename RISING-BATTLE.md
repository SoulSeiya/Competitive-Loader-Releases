# Rising Battle 1.5.3 — Dragon Net Battle, salas y torneos

## Entrar y probar

Abre el Loader 1.5.3. En **F1 → Online → Dragon Net Battle** verás **Partidas** y **Torneos BTC**. Partidas conserva Host, Quick match y Join con sus códigos nativos, reglas y FT. La entrada Tenkaichi Budokai Online también abre Torneos BTC como acceso alternativo.

En Torneos BTC, pulsa **Crear prueba: tú + 3 bots, todos contra mí**. Se crean cuatro inscritos y una sala del servicio local con código BTC de seis caracteres. Se propone FT1; puedes cambiar nombre y FT, guardar e iniciar la prueba. Jugarás tres sets consecutivos, uno contra cada bot, incluso si pierdes. Tú conservas P1 y el control de menús. Los bots confirman y usan entradas programadas de movimiento, golpes y ki; no son IA avanzada ni cambian el daño.

La prueba Todos contra mí es un circuito de laboratorio, sin eliminaciones ni campeón. El torneo normal conserva el sorteo, bracket de 2–32 inscritos y pases libres. El chat anuncia cruces, resultados y campeón. Cada set avanza cuando ambos jugadores entregan el mismo marcador válido. Los resultados repetidos no cuentan dos veces; los contradictorios requieren revisión o WO del anfitrión.

## F2 y Tab

**F2** muestra u oculta el bracket actualizado de la sala, también durante el combate. Es una vista de consulta: no pausa ni toma el teclado del juego. En Todos contra mí muestra los tres sets y sus estados.

**Tab** reutiliza el chat nativo del juego y lo conecta a todos los miembros de la sala. No hay un segundo chat dentro del panel de torneo. Enter envía; Esc/Tab cierra. Desde la pestaña de torneo, Tab cierra el panel y abre el chat. La inscripción, las reglas y los anuncios siguen sincronizados durante las peleas. Fuera de una sala BTC, el chat conserva su funcionamiento nativo entre los dos jugadores.

## Room codes de sala

El servicio BTC propio mantiene varias personas conectadas bajo **BTC-XXXXXX**. Para varios Loaders de este equipo, pulsa **Iniciar servicio local de prueba** en uno, usa su URL local en todos, crea una sala y comparte su código. La prueba automática de bots puede iniciar un servicio en un puerto libre; su URL aparece junto al código. Cerrar el Loader que aloja ese servicio local lo termina.

Los códigos nativos de Dragon Net Battle siguen enlazando exclusivamente a los dos jugadores de cada combate. El código BTC pertenece a la sala completa y no se consume al empezar una pelea. La conexión directa avanzada por IP/VPN e invitación BTC1 continúa disponible.

El coordinador está probado localmente. En 1.5.3 puedes publicarlo temporalmente desde tu PC con el iniciador del anfitrión y compartir su dirección HTTPS. El alojamiento permanente y la prueba manual entre dos equipos siguen pendientes. Véase service/PRUEBA-CON-AMIGOS.txt. No se distribuye ni retransmite contenido del juego.

## Límites y registros

El anfitrión configura temática, FT1–FT5 y de 1–5 personajes declarados. La inscripción valida nombres y cantidades, pero aún no restringe los personajes elegidos dentro del combate. Cambiar ese límite reinicia las inscripciones. El anfitrión puede expulsar, resolver WO y cancelar el torneo. Salir o perder conexión provoca WO; salir el anfitrión cierra la sala.

**Ver combate local de bots** permite mostrar otra instancia propia cuando el anfitrión espera. Todos contra mí te mantiene jugando y no cubre esa espera. El espectador online por replay aún no está implementado.

Cada bot usa runtime, save y proceso propios; solo arranca cuando le toca. Se retiran exclusivamente sus procesos mediante jobs de Windows. El humano usa una copia aislada del save en el candidato preparado. Los datos se leen de la instalación competitiva. Los registros y hashes quedan en logs/tournament-lab, excluidos de Git; no se suben automáticamente.

El servicio guarda estado en memoria: reiniciarlo elimina sus salas. Hay pruebas de protocolo, cuatro clientes, autorizaciones y torneo completo; no se ha probado todavía entre equipos por Internet ni bajo carga pública. El puente entre Loader y juego usa ABI 5; la red se realiza fuera del hilo de renderizado.

## Matchmaking propio activo en 1.5.2

La versión 1.5.2 usa por defecto nuestro Worker Cloudflare:
https://btc-matchmaking.paulogomez41.workers.dev . No recurre al matchmaking oficial
del decomp. La dirección se aplica también a los bots. El botón Configurar
matchmaking BTC permite cambiarla; guardar vacío desactiva los códigos de pelea.
La cuenta mantiene el plan gratuito y no tiene TURN configurado.

Se verificaron Host/Join por HTTPS y conexión de dos instancias reales del juego
a través del Worker propio. La sala de torneo sigue usando el coordinador local;
el Worker publicado enlaza solo las peleas. El espectador y la sala pública del
torneo siguen pendientes. La guía está en service/cloudflare-matchmaking.

## Prueba con amigos 1.5.3

El paquete del anfitrión incluye Iniciar servidor de prueba.cmd y cloudflared.exe.
Ejecuta ese iniciador, pulsa Iniciar servidor de prueba y deja la ventana abierta.
Cuando el túnel conecte, aparecerá una dirección HTTPS temporal; se guarda en la
configuración del Loader de esa carpeta. Inicia el juego después de este paso.
Comparte la dirección con tu amigo, quien debe guardarla en Configurar servicio
de salas BTC del Loader antes de iniciar su juego. Ambos usan Dragon Net Battle →
Torneos BTC. Crea sala, comparte BTC-XXXXXX y usa Tab para conversar y F2 para
consultar el bracket. El host puede añadir bots de sala, retirarlos y expulsarlos.

Este servidor temporal depende de tu PC. Al cerrar el iniciador, detenerlo o
apagar el equipo se pierden las salas. Al reiniciar el túnel cambia la dirección:
hay que volver a compartirla y guardarla. Solo se publica la API del coordinador;
no se retransmiten ISO, memory ni archivos personales. Es una prueba provisional,
no el alojamiento permanente de torneos. Los bots añadidos en la sala simulan
usuarios/listo/chat/inscripción; no juegan combates. La prueba local de tres bots
reales de combate sigue disponible aparte en Laboratorio.
