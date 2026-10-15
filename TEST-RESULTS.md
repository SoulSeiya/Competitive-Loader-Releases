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
