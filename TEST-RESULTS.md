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

## Corrección posterior de la apertura gráfica

Tras incorporar la interfaz experimental se reportó un fallo en el vídeo de apertura. La intro competitiva incluía fotogramas P/B y esta interfaz había omitido su conversión, aunque el decodificador oficial sigue reconstruyendo solo imágenes I. Se restauró la conversión únicamente en el arranque gráfico y se incluyeron el conversor y sus licencias en ese EXE.

Se preparó la copia compatible de la instalación local, conservando ZS3USOP.original.PSS. Una comprobación compilada con plat_mpeg2.c de 0.1.35.2 recorrió el archivo convertido: 2.472 cuadros decodificados y 2.295 cambios de imagen a 512x448. La segunda llamada al preparador reutilizó el vídeo sin modificarlo. El EXE gráfico actualizado pasó la comprobación de apertura de interfaz. No se repitió una partida online por este cambio del vídeo de apertura.

## Audio de la interfaz experimental

Se añadió competitive_audio.o como único wrapper de audio, independiente de competitive_chat.o. Recorta la reproducción AFS2 al encontrar una marca de fin CRI bajo el bloqueo del stream. Solo utiliza el prefijo revisado del Player, no sizeof(Player), no indexa sPlayers y no escribe gPortAdxView ni archivos de audio. Se mantiene fijado el SHA-256 del decomp compatible.

Las pruebas nativas verificaron EOF mono/estéreo, alineación de cabeceras, fallo del bloqueo, alcance AFS2, un Player de mayor tamaño y conservación de los bytes originales. Tres ADX de la instalación competitiva confirmaron el recorte de muestras: 49083.bin, 148669 a 116608; 49085.bin, 144143 a 116512; 49092.bin, 173991 a 116576. El payload con audio resolvió todas las referencias. La apertura del EXE gráfico pasó; el arranque real de verificación aplicó 17 entradas y un wrapper de audio. No es una prueba de escucha ni una validación online de esta revisión.

## Tiempos competitivos del menú online

La interfaz gráfica activa competitive_times.o: cambia los valores reales 60/90/180/240 por 180/240/360/480 antes del cargador oficial de batalla, únicamente en sesión online. Al cargar offline restaura los valores originales. No cambia el índice que transmite la red ni la opción sin límite. Se restauraron también las cuatro etiquetas del menú online. Las pruebas nativas comprobaron los cuatro valores antes de Battle_Load, cargas repetidas, restauración offline y conservación del resto de entradas. Se verificaron la resolución completa del payload y una sola aparición de cada etiqueta en el ejecutable fijado. La prueba online original conserva su perfil sin estos cambios; no se certifica todavía el temporizador en una sesión real de dos jugadores con esta revisión.

## Release 1.1.0 y diagnósticos

Se añadió una prueba de descarga completa simulada (ZIP, extracción y validación) con un decomp desconocido: la instalación previa conservó su ejecutable y no se llamó a la sustitución transaccional. Otras pruebas verifican separación de mensajes de red/locales, detección del mensaje nativo de desync y copia exclusiva de un informe de crash nuevo.

En una prueba de arranque real se aplicaron 17 entradas competitivas, dos wrappers y 67 ramas directas. El proceso permaneció abierto ocho segundos y se cerró de forma controlada para verificar el monitor. Se guardaron local.log (13.772 bytes), online.log (2.341 bytes), patch.log y session.json con status closed y exit_code 0x00000000. Esta prueba confirma captura real y seguimiento de salida; no es una prueba de crash real ni una nueva partida online prolongada.

La primera ejecución de GitHub Actions detectó una aserción de ruta que distinguía RUNNER~1 de runneradmin aunque fueran la misma carpeta. Se corrigió usando identidad de archivo/carpeta y el siguiente trabajo de Windows pasó. Se añadió además una prueba para conservar el estado de un proceso que termina inmediatamente en lugar de sobrescribirlo como operación completada. Las 14 pruebas locales del paquete final pasan.


## Marcador, ventana y novedades 1.2.0

Se corrigió la carga de secciones COFF BSS: su tamaño representa memoria sin inicializar y PointerToRawData=0 no apunta a datos del archivo. Una regresión comprueba que los locks y el estado del observador empiezan en cero. El reinicio de ronda se detecta mediante el resultado nativo limpio, porque Battle_Restart está integrado en sus llamadores y no tiene llamadas directas que redirigir.

El contador nativo pasa pruebas de victorias consecutivas, confirmación, resultado corregido por rollback, empates, abortos y reinicio de sesión. Las 17 pruebas Python/nativas locales pasan, incluido el aviso que solo aparece una vez por versión. El panel tiene una ruta de dibujo adicional cuando la interfaz oficial omite su frame por no haber menús ni avisos.

La prueba automatizada anterior a esa ruta de dibujo comparó 15.967 blanks comunes, incluidos 13.451 de combate, con rollback máximo 8, delay 2, latencia simulada 15 ms y pérdida 1 %. No hubo diferencia observada de vida, posición o reloj ni aviso nativo de desync. No terminó una pelea, por lo que no valida victorias consecutivas. El primer arranque de laboratorio carecía de SDL3.dll y luego de la lista .exe.mem; se copiaron ambos archivos oficiales antes de esta medición. Las capturas de Windows fallaron por timeout y no se ha confirmado visualmente el panel.

Se dejó una prueba manual con dos instancias aisladas: host con controles reales y guest con confirmación Cross cada 120 blanks, sin ataques. Usa el perfil de Release completo y conserva game.log, state-hashes.txt y los PID/códigos de salida en cada runtime. La prueba completó tres victorias: ambos extremos registraron 1–0 en tick 7854, 2–0 en 12280 y 3–0 en 17762. Se compararon 21.600 blanks comunes (15.622 de combate), sin diferencias observadas de vida, posición o reloj. Las capturas automáticas de Windows siguieron sin funcionar, así que no se afirma una revisión visual del panel.


Al abandonar esa prueba, el arranque directo con BT3_NET_SESSION produjo 0xC0000005: no había pasado por la petición de sesión que guarda el estado de retorno. El perfil de laboratorio --release-profile ahora pide la sesión desde un arranque normal mediante la ruta nativa BT3_SESSION_TEST. La comprobación de 100 segundos con el payload final entró cinco veces y registró cuatro retornos al menú, con activación/liberación del bloqueo de ventana en ambos extremos, sin aviso nativo de desync ni repetición del cierre incorrecto. Ambos procesos terminaron con parada controlada 0x0.

La prueba adicional tests/test_window_native.cpp se compiló y ejecutó con SDL3: creó su propia ventana oculta y comprobó el procedimiento HWND real, bloqueo de movimiento/tamaño y F11, paso de controles normales, restauración offline y destrucción de la ventana. Se probaron también la apertura de la GUI empaquetada y la resolución del payload desde el EXE congelado: ambos códigos de salida fueron cero. Estas pruebas locales finitas no garantizan ausencia de desync en Internet.


## FT y búsqueda manual de actualizaciones 1.3.1

Las pruebas nativas cubren FT1 a FT5, empate sin avance, punto de set confirmado, rechazo de victorias adicionales, corrección por rollback del ganador aparente y reinicio de sesión. Se comprueban también los bits de FT en el campo de reglas sin alterar tipo, DP, tiempo o velocidad, y el rechazo de objetivos inválidos. La nueva prueba de consulta manual verifica dos búsquedas consecutivas y evita consultas superpuestas. Las 19 pruebas pasan.

Una prueba con dos procesos reales usó la petición nativa de sesión, rollback 8/delay 2 y FT1. Para acelerar el combate automatizado se eligió velocidad nativa 200 % en el laboratorio; la GUI conserva su selector original. Se verificó por lectura que ambos recibieron sRules=0x00C82000 (FT1). Ambos confirmaron el 1–0 en tick 9951 y registraron que dibujaron el panel GG/ganador. La segunda instancia ejecutó la salida de FT y la primera recibió la despedida nativa; ambas liberaron el bloqueo y retornaron al menú sin desync notificado. Se cerraron después únicamente los dos procesos de la prueba con código cero. Es una prueba funcional local, no una garantía sobre cualquier conexión de Internet.

El ajuste FT de Host se añade a la fila identificada de la interfaz F1 del ejecutable revisado; se resuelven Combo y TextDisabledV con los headers de ImGui de esa misma versión. No se recompila ni sustituye el menú online completo. La conexión usa los bits 13–15 de las reglas nativas, preservados por los mensajes de configuración existentes. El perfil de búsqueda rápida no hereda el FT del Host. La fila de conexión se muestra en los menús 2D online para cubrir selección individual y por equipos.

La prueba de integración de FT ejecuta el módulo de reglas y la fila Host con dobles del motor/UI: verifica la selección persistente, paso de argumentos variádicos y la limpieza del FT al entrar en Quick match (el menú ya había establecido las reglas antes de esa llamada). La revisión 1.3.1 contiene esta corrección para que el FT privado no se herede en búsqueda rápida.


## Modelos embebidos 1.3.2

La sesión reportada usaba Loader 1.3.1 y el decomp revisado; no observó conexión online. La dirección +0x33D16D corresponde a BtlObjMdl_BindFiles+0x1D, leyendo modelo+0x6C con modelo nulo; la cadena anterior incluye EftPropShot_InitProp y EftObj_Create. Se confirmó en el código que este último fija file[0].size=0x20 para un modelo embebido. Nuestro BObjFile_GetEntry y su copia integrada en BindTables usan ese campo para comprobar límites y rechazaban así entradas válidas.

La nueva extensión envuelve BtlObj_Create, identifica únicamente el descriptor sintético de efecto, busca la asignación activa del heap y recupera un tamaño acotado (la longitud del pack cuando su tabla la describe, o el límite restante de la asignación). Valida la cabecera del modelo dentro de ese límite. Conserva el constructor original y el acceso comprobado a las tablas.

Las 20 pruebas pasan. El nuevo caso nativo reproduce que un descriptor size=32 produce modelo vacío con el comprobador anterior, y que la corrección conserva el modelo válido sin extenderse fuera de su asignación. Comprueba recursos normales sin cambios, bloques liberados y descriptores truncados. Pasaron arranque de la GUI y resolución del payload empaquetado con la instalación reportada. Una demo real sin ventana alcanzó 600 blanks sin crash y terminó mediante parada controlada 0; no ejecutó el ataque específico y no valida todavía ese efecto en el juego. Validación manual del 15 de octubre de 2026: el usuario repitió el ataque 1 de Androide 16 con el candidato 1.3.2 y confirmó que funcionó. Esta confirmación cubre el fallo reportado; no constituye una prueba exhaustiva de todos los efectos.


## Rising Battle 1.4.0 — salas, candidato local

Las 28 pruebas pasan. La nueva cobertura comprueba invitaciones y protocolo BTC, nombres duplicados, capacidad, autorización del anfitrión, revocación del usuario expulsado, estado listo, chat y límite del historial, caducidad de participantes y cierre del anfitrión. Incluye peticiones HTTP reales entre anfitrión y dos clientes, rechazo de cuerpos malformados o demasiado grandes, y dos puentes de memoria compartida independientes comunicados por HTTP: roster, chat, listo y expulsión observada por el invitado.

La comprobación adicional tests/test_room_ui_native.cpp se compiló con los cuatro archivos principales de ImGui 1.92.9b del decomp revisado, SDL3 y Windows. Dibujó frames reales sin ventana visible y usó el puente del Loader para crear una sala, enviar chat, marcar listo y cerrarla; salida cero. Los tamaños C++ y Python de la interfaz compartida coinciden. La resolución completa del payload no dejó símbolos pendientes. El ejecutable revisado tiene una llamada directa a build_net y veinte a ImGui::Begin, cubiertas por los wrappers.

Una instancia propia del juego real, usando el runtime de laboratorio, abrió el menú Rising Battle mediante la petición nativa de menú online y registró la conexión al puente del Loader. El proceso continuó estable y se cerró únicamente esa instancia de prueba mediante parada controlada. Registro: online-tests/score-001/host/room-menu-smoke.log, fuera del repositorio. No se han verificado visualmente la distribución y los controles en la pantalla del usuario.

El EXE congelado pasó --smoke-test, --smoke-runtime y --smoke-room con salida cero. Este último crea una sala exclusivamente en loopback y comprueba entrada, chat y expulsión con los módulos realmente empaquetados; también queda integrado en GitHub Actions. No hay todavía una prueba entre equipos por Internet ni validación con 32 usuarios concurrentes. La capacidad es un límite de sala, no una cantidad admitida de jugadores en un combate.

El candidato conserva la conexión nativa de combates de dos jugadores, FT y el marcador. No implementa todavía espectadores, relevos, brackets ni anuncios automáticos de cruces de torneo.


## Corrección de alcance y bots 1.4.1 — desarrollo

El usuario aclaró que Dragon Net Battle debe conservarse: el objetivo es adaptar Tenkaichi Budokai Online, bloqueado por datos modificados, a un sistema BTC de salas/torneos. La ruta normal de build_net vuelve a su función original y el wrapper de ImGui::Begin reenvía su nombre sin cambios. El panel de pruebas solo se activa con su botón explícito de desarrollo en Settings/F1. Esta revisión no integra todavía la sala en el modo TBO ni elimina su comprobación global de datos originales.

Las 33 pruebas pasan. Nuevos casos validan invitaciones BTC1, corrupción y entrada HTTP por invitación; bots autorizados solo por el anfitrión; sala completa con 31 bots más el anfitrión; mensajes, cambios de listo, expulsión sin reconexión automática y retirada de bots. Dos puentes Windows verifican entrada con código, gestión de bots y rechazo de un invitado que intenta añadirlos. La ABI de memoria compartida pasa a versión 2, con tamaños C++ y Python coincidentes.

La prueba nativa con ImGui/SDL reales pasa: primero comprueba que la entrada normal delega a Dragon Net Battle, activa expresamente el panel de desarrollo y prueba creación, invitación, chat, listo, tres bots, retirada y salida. El juego real de laboratorio también registró primero la ruta nativa preservada y después el panel provisional con su puente conectado, permaneciendo estable hasta una parada controlada de esa única instancia.

La invitación BTC1 incorpora una dirección y no sustituye el servicio público de códigos cortos solicitado. Se ha investigado Cloudflare Workers/Durable Objects y el dominio workers.dev; todavía no existe cuenta, despliegue ni endpoint público. Las pruebas locales no comprueban NAT, relay, Internet, espectadores ni torneos completos.

## Rising Battle 1.5.0 — candidato local, 15 de octubre

El modo TBO abre Rising Battle; Dragon Net Battle conserva su ruta original. El motor genera brackets de 2–32 inscritos, pases libres y resultados confirmados por ambos jugadores. La prueba local Todos contra mí prepara al humano y tres bots de combate, programa tres sets y conserva al humano después de perder. No se presenta como un torneo de eliminación.

Las 45 pruebas pasan con el toolchain local. Cubren todos los tamaños del bracket, seis inscritos con dos pases, autorizaciones, resultados repetidos/contradictorios, inscripción, WO y circuito de cuatro con tres derrotas humanas consecutivas. El puente real de Windows verifica cuatro miembros, tres bots de combate, FT1, tres cruces con el humano P1 y cierre del gestor. Una prueba de jobs comprueba que cerrar el job de un auxiliar no termina otro proceso ajeno al job. La ABI C++/Python versión 4 coincide.

La fixture nativa compilada con ImGui/SDL reales pasa: dibuja frames, preserva Dragon Net Battle, administra la sala y el bracket, comprueba el bucle TBO, pads automáticos, roles, publicación/recepción de código nativo y entrega del marcador FT. Una instancia propia del juego real también entró al modo TBO, completó un bracket simulado de seis bots y volvió al menú. Estas pruebas no son una revisión visual de la interfaz.

Dos clientes reales de bots conectaron por el matchmaking nativo, seleccionaron personajes y combatieron. El primer ensayo finito de 240 segundos no llegó a confirmar el FT; no se considera una validación del cierre. La prueba humana de tres sets consecutivos y el retorno a sala quedan pendientes de ejecución manual. El espectador online por replay, la restricción de personajes en combate y los códigos públicos de sala BTC siguen sin implementar.

El ensayo real posterior terminó con éxito: dos bots completaron FT1, ambos registraron P1=0/P2=1 en el tick confirmado 13989, mostraron el panel GG y entregaron sus resultados coincidentes al servicio de sala, que marcó campeón. Evidencia local: logs/tournament-lab/a867c82843f24d1483012e1a48388440 (excluida de Git). Esta prueba cubre un set real; la secuencia de tres rivales humanos sigue pendiente de prueba manual. El EXE congelado pasó --smoke-test, --smoke-room (incluye inscripción/inicio/cierre de torneo por HTTP) y --smoke-runtime contra el runtime aislado de la prueba.

## Rising Battle 1.5.1 — códigos propios, pestaña, F2 y chat nativo

El coordinador rising_service.py mantiene múltiples miembros en cada sala bajo un código BTC-XXXXXX. Es un servicio propio; no modifica el matchmaking oficial ni intenta ampliar sus salas de dos jugadores. La conexión de cada combate sigue usando la API nativa. El servidor está probado únicamente en loopback; no se ha desplegado en Internet ni se ha ejecutado la receta Docker preparada.

Pasan 50 pruebas. La nueva cobertura conecta cuatro clientes HTTP por el mismo código, comprueba difusión del chat, inscripciones, bracket completo y coincidencia de resultados, permisos del anfitrión, expulsión y cierre. Otras pruebas verifican 32 miembros y rechazo del 33, aislamiento entre códigos, expiración, limitación de admisiones y rechazo de HTTP remoto o URLs con credenciales. La prueba con tres bots usa ahora el coordinador local y un código BTC. Una prueba de publicación forzada detecta y evita confirmar un comando antes de que su estado esté visible en la memoria compartida; se corrigió esa carrera. La ABI pasa a versión 5.

La fixture nativa ImGui/SDL pasa y verifica además la pestaña de Dragon Net Battle, el atajo F2 sin doble alternancia por repetición/keyup, envío y lectura del chat de sala mediante los wrappers de PortChat, conservación de los métodos originales fuera de sala y que la extensión del estado online esté limitada al contexto UI. Cerrar la ventana no cancela la conexión asignada por el bracket.

Una instancia propia del juego revisado pasó una prueba instrumentada: pestaña Torneos seleccionada en la ventana nativa, sala de cuatro clientes por código, overlay de bracket y chat nativo activo fuera de combate durante varios frames. Se verificó que la lógica nativa no cerrara el chat por no existir un combate online. Registro local: online-tests/score-001/host/social-smoke-fb2cf531.log. La fixture modifica únicamente variables de su propia instancia de laboratorio y la termina de forma controlada. No es una revisión visual ni una prueba manual del teclado en el equipo del usuario.

El alojamiento HTTPS público, pruebas entre equipos y el espectador online por replay siguen pendientes. El servicio conserva estado solo en memoria; al reiniciarlo se pierden sus salas.

El EXE congelado 1.5.1 pasó --smoke-test, --smoke-room, --smoke-service y --smoke-runtime con salida cero. --smoke-service usa los módulos empaquetados para crear una sala por código y conectar cuatro miembros en loopback. El candidato local preparado conserva un runtime humano separado; la prueba manual de tres sets y revisión visual sigue pendiente.

## Matchmaking propio 1.5.2 — Worker desplegado

El Loader fija BT3_MATCH_URL en todos los procesos de Release, incluidos los bots. Por defecto usa https://btc-matchmaking.paulogomez41.workers.dev; un endpoint propio válido se conserva. Guardar el campo vacío desactiva explícitamente los códigos mediante loopback y muestra el aviso. No hay fallback al dominio del decomp. El diálogo conserva el resto de la configuración y no cambia procesos ya iniciados.

Pasan 54 pruebas Python. Los nuevos casos cubren la URL propia predeterminada, loopback, desactivación explícita, rechazo del dominio oficial, HTTP remoto, credenciales/rutas/parámetros y preservación de preferencias. Las 95 comprobaciones upstream del Worker fijado en 5b0ad7ed1513fd99de6d4bdd2719c917acbf672e pasan sin red, con un adaptador ESM para Windows. Fuente, esquema y licencia MIT originales se descargan con manifiesto de hashes en una carpeta excluida de Git. La fixture nativa con ImGui/SDL comprueba también el bloqueo del enlace automático cuando se desactivan los códigos.

El Worker btc-matchmaking está desplegado en la cuenta del usuario con D1 btc-matchmaking-rooms vinculada como DB y las tablas rooms/used creadas. MIN_RELEASE y LATEST_RELEASE valen 135. La prueba HTTPS creó un código, conectó otro cliente, comprobó los peers recíprocos y retiró la sala de prueba. No se configuraron BUILD_KEYS, TURN ni planes de pago.

Dos bots del juego real conectaron mediante el Worker propio y ambos logs confirmaron esa URL. Se observaron unos 535 checks confirmados durante el ensayo finito; no terminó un FT. Evidencia privada local: logs/tournament-lab/81649658e74f489b9d935ebc22c1990d. Esto verifica el enlace de dos instancias, no una pelea completa entre redes distintas ni NAT restrictivo.

Una comprobación adicional del ejecutable revisado con BT3_SIGN_TEST=post recibió /v1/hello en loopback y terminó con código cero. Registro privado: online-tests/score-001/host/btc-matchmaking-url-smoke.log. La sala pública de torneo y el espectador remoto por replay siguen pendientes; el nuevo Worker solo enlaza combates 1 vs 1.

El paquete final 1.5.2 pasó --smoke-test, --smoke-room, --smoke-service y --smoke-runtime con salida cero tras reconstruirse con la URL pública predeterminada. Se copió el mismo EXE a bin y al candidato local Competitive-Rising-Battle-1.5.2. La secuencia manual del humano contra tres bots y la revisión visual siguen pendientes.

## Prueba de salas con amigos 1.5.3 — paquete preparado

Pasan 59 pruebas. Dos clientes HTTP reales comprueban que solo el host pueda añadir o retirar bots del coordinador, que los invitados reciban sus mensajes/estado, que un bot expulsado no reaparezca y que la salida/caducidad del host cierre la sala. Los bots de sala no juegan combates. Un reloj controlado verifica que mantenerlos presentes no prolongue la sesión del anfitrión ausente. La configuración de servicio conserva el runtime. El iniciador temporal espera una conexión registrada antes de guardar su URL y su cierre solo termina los Popen propios, con cancelación del monitor.

La fixture nativa con ImGui/SDL pasa después de recompilar el payload. El EXE congelado pasa --smoke-test, --smoke-room, --smoke-service, --smoke-runtime y --smoke-room-test-host, todos con salida cero. Este último abre/cierra el controlador sin iniciar procesos ni publicar servicios.

Se preparó un ZIP para invitados con lista explícita de archivos públicos: EXE, guías y licencias. Se verificaron su integridad y el hash del EXE; no contiene configuraciones, logs, ISO ni memory. La carpeta exclusiva del host contiene el mismo EXE y cloudflared 2026.10.1 del repositorio oficial, con licencia Apache 2.0. Hash SHA256 del helper: 4d2490e74082c5d48dbfedaf92576fa5bd1702379ab88eb7faa0cfbe8dc891b6.

La revisión automática bloqueó el comando de arranque del servicio y Quick Tunnel, sin aportar motivo concreto. No se repitió por otro mecanismo. El túnel no está iniciado: el usuario debe abrir Iniciar servidor de prueba.cmd y pulsar Iniciar. La prueba manual con el amigo por Internet, la operatividad real de ese túnel y la revisión visual siguen pendientes. No se publicó una Release.

## Replay local P1/P2 y separación del laboratorio 1.5.4

Pasan 62 pruebas. La prueba nativa de cámara comprueba las vistas 0/1 y layout dividido únicamente con replay activo offline, con paso íntegro a la cámara original fuera de ese contexto, online y durante cinemáticas. Verifica además la configuración CPU/CPU limitada al proceso de grabación y el modo HUD. La preparación del archivo conserva las pistas byte a byte y solo cambia screenMode; rechaza tamaño/formato/pistas inválidos. Se corrigió durante el ensayo el padding final de 0x20 que exige el cargador nativo.

Se grabó un clip real CPU/CPU y se reprodujo mediante BT3_REPLAY con ambas cámaras. La captura GPU confirmó dos perspectivas distintas en una sola imagen. En ocho muestras comunes de vida, posición y reloj, el replay coincidió con la grabación; es una observación finita, no una prueba exhaustiva de determinismo. Evidencia local privada: logs/replay-spectator/0e2c11ebab4e4ffa855bf7c0704da498 y bf6a7c3dae9c4985b9faf48902c7bc65. Los ensayos visuales finitos posteriores se cerraron solo en sus procesos propios. Un replay Versus agotado permanece en el estado final hasta cerrar su ventana.

La fixture nativa de sala ImGui/SDL pasa. El menú normal oculta crear bots, simulación, servicio local y vistas de otras ventanas de prueba. El inicio normal limpia las variables de laboratorio heredadas; los ensayos las pasan explícitamente. La prueba local se entrega en una carpeta distinta, con un acceso que abre el replay mediante --watch-replay. No se incluye ese acceso ni el clip en el ZIP normal.

La recepción de entradas online, incorporación tardía de espectadores y asociación del visor con el bracket siguen pendientes. No se ha publicado una Release ni se presenta esta reproducción local como espectador online ya implementado.

El EXE final 1.5.4 pasó --smoke-test, --smoke-room, --smoke-service y --smoke-runtime con salida cero. Se ejecutó también su ruta --watch-replay y se confirmó la entrada en la cámara dividida desde el log del juego. Ese ensayo empaquetado se detuvo cerrando únicamente el job propio del visor.

## Candidato 1.5.5 — prueba con dos humanos y dos bots

El ensayo local previo de tres entró en una semifinal real con las cámaras P1/P2 activas y comparó 1578 muestras de combate sin diferencias observadas. La inspección posterior descubrió que la opción pedida no fijaba el índice final: la tabla contenía 180 en la entrada 1, pero el setup usaba la entrada 3 (360). Se detuvo el ensayo y se corrigió Competitive_TimeBattleLoad para aplicar la opción negociada al setup real y a su copia de replay antes de cargar la batalla. La regresión cubre las cinco opciones, rematch y retorno offline.

El intento posterior de publicar el código de combate desde un ServiceClient reveló una colisión entre el código de sala y el código del cruce. Se separan en room_code y code, conservando compatibilidad con admisiones anteriores. Una prueba HTTP reproduce la publicación y recepción sin perder la identidad de sala.

El usuario pidió sustituir el ensayo largo por un paquete para dos personas y dos bots. El coordinador del modo explícito de prueba crea los bots de combate en el PC host, prepara ambos cruces humano/bot y garantiza una final humana incluso tras perder contra bots. La prueba HTTP con el gestor de procesos sustituido comprueba esas dos derrotas y la final, autorizaciones y cierre. Las peleas reales de ese recorrido y el túnel entre ambos equipos quedan para su prueba manual. No se afirma que ese torneo completo ya se haya jugado ni que exista espectador remoto.

Pasan 67 pruebas locales. La comprobación del EXE congelado verificó la GUI, salas, servicio, controlador de host y resolución del payload. El servicio empaquetado en loopback registró dos clientes humanos y dos bots de combate, con cuatro inscritos y FT1; no inició las peleas en ese smoke. El túnel público debe arrancarlo el usuario desde el controlador.
