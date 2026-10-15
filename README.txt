COMPETITIVE LOADER
=======================

Objetivo
--------
Permite usar DBZ Competitive Edition v8.4.1 con una instalación oficial ya
construida de Tenkaichi3Decomp para Windows x64, sin recompilar el proyecto.

La herramienta NO modifica:
  - la ISO competitiva;
  - el ZIP o la carpeta oficial;
  - el ejecutable oficial original.

Prepara una copia aparte llamada CompetitiveRuntime. Al iniciar, el parche
nativo se aplica únicamente al proceso en memoria y desaparece al cerrarlo.

Primer uso
----------
1. Ejecuta "Competitive Loader.exe".
2. Pulsa "Jugar Competitive" y elige tu ISO
   "DBZ Competitive Edition v8.4.1_crc.iso".
3. El cargador descarga y comprueba automáticamente la última publicación
   oficial Windows x64 de Tenkaichi3Decomp.
4. Opcionalmente, elige una memory `.ps2` de PCSX2 para importarla antes del
   primer inicio. También puedes omitirla e importarla después.
5. Espera la extracción inicial. Requiere aproximadamente 3.5 GB libres.

IMPORTANTE: no abras CompetitiveRuntime/Tenkaichi3Decomp.exe directamente.
Siempre inicia con "Competitive Loader.exe", porque el parche se aplica en
memoria durante ese arranque.

Actualizaciones automáticas del decomp
--------------------------------------
No hay que pulsar un botón separado. Cada vez que usas "Jugar Competitive",
el cargador consulta primero cuál es la última publicación oficial Windows x64.
Solo descarga el ZIP cuando GitHub tiene una versión distinta. La actualización
se comprueba antes de instalarla y conserva los datos de la ISO, la partida,
texturas, canciones y escenarios.

Si GitHub no responde, se muestra un aviso y se inicia la versión que ya está
instalada. Una publicación incompatible no reemplaza la copia funcional.

Actualizaciones de Competitive Loader
-------------------------------------
Al abrir la aplicación se consulta la última Release publicada en el
repositorio público de distribución `SoulSeiya/Competitive-Loader-Releases`.
Ese repositorio contiene las publicaciones y ahora también el código del Loader.
Si existe una versión posterior, el botón superior muestra
"Actualizar Loader". La descarga e instalación solo comienza al pulsarlo;
después el loader se reinicia con la versión nueva.

Solo reemplaza "Competitive Loader.exe": la ISO extraída, la memory,
CompetitiveRuntime y los ajustes locales permanecen intactos. Si el juego está
abierto, el botón pide cerrarlo antes de instalar de forma segura.

La pantalla principal muestra por separado:
  - la versión más reciente del decomp disponible en GitHub;
  - la versión del decomp instalada localmente;
  - la versión más reciente de Competitive Loader disponible en GitHub;
  - la versión de Competitive Loader que se está ejecutando.

Importar una memory de PCSX2 (opcional)
---------------------------------------
Esta función no se ejecuta durante el inicio normal. Cuando quieras actualizar
la partida, pulsa "Importar memory PCSX2" y elige la tarjeta .ps2.

El importador busca BASLUS-21678DBZT3, verifica su tamaño y checksum, respalda
la partida anterior en CompetitiveRuntime/save-backups/ y después instala la
nueva. Cierra PCSX2 y Tenkaichi3Decomp antes de importarla.

Memory competitiva en online
----------------------------
Antes de iniciar el juego, Competitive Loader copia la partida instalada a
"net_session" y mantiene abiertos sus tres archivos sin permiso de borrado.
Tenkaichi3Decomp puede leerlos y escribirlos, pero su limpieza automática no
puede eliminarlos. Así el online arranca con los ajustes de balance guardados
en la memory, sin recompilar ni modificar el ejecutable oficial.

IMPORTANTE:
  - ambos jugadores deben importar exactamente la misma memory;
  - el juego compara automáticamente el SHA-256 completo de ambos jugadores;
  - mantén Competitive Loader abierto durante toda la sesión online;
  - memories distintas pueden causar una desincronización.

El SHA-256 también se guarda en CompetitiveRuntime/ONLINE_MEMORY_SHA256.txt.

Chat y pausa durante una partida online
----------------------------------------
Durante una sesión online, pulsa T para escribir. Introduce el mensaje y pulsa
Enter para enviarlo; Escape lo cancela. Un cuadro sobre el juego conserva las
dos líneas más recientes y muestra lo que estás escribiendo. Los dos jugadores
necesitan Competitive Loader v0.14 o posterior para ver y enviar mensajes. Un
decomp sin el loader ignora estos paquetes y la partida continúa normalmente.
Mientras el chat está abierto, F2 envía "Listo", F3 "Espera un momento",
F4 "Buen combate" y F5 "Gracias". Estas teclas rápidas solo se capturan dentro
del cuadro de chat. F1 queda reservado para el menú propio del decomp.

START queda bloqueado mientras la sesión online está activa. Así ninguno de los
dos jugadores puede abrir localmente un menú de pausa que el rollback no puede
sincronizar. Fuera del online, START conserva su funcionamiento normal.

Mientras el online está activo también quedan bloqueados F11, mover o cambiar
el tamaño de la ventana, minimizarla y maximizarla. Estas acciones hacen que
Windows detenga temporalmente el hilo principal y pueden congelar o desincronizar
la partida. Al terminar la sesión online, la ventana recupera todos sus controles.

Roster y tiempos online
-----------------------
Antes de mostrar la selección aparece el estado Listo/Cargando de ambos
jugadores y la comprobación de versión del Loader y memory. Durante la selección
aparece una placa con ambos nombres, compatibilidad y el marcador acumulado de
la sesión. El marcador continúa al usar la revancha propia del juego.
Las cuatro opciones con límite usan los tiempos Competitive y la interfaz
muestra su duración real:
  - 60 pasa a 180 segundos;
  - 90 pasa a 240 segundos;
  - 180 pasa a 360 segundos;
  - 240 pasa a 480 segundos.
"Sin límite" no cambia. Fuera de una sesión online se restauran los tiempos
originales del juego.

Corrección de audio AFS2 e intro
--------------------------------
Algunos ADX modificados del AFS2 terminan antes del relleno que conservan al
final. El Loader respeta la marca de fin CRI para que ese relleno no se
interprete como audio saturado. No reduce el volumen ni modifica los archivos.

El reproductor MPEG compacto del decomp solo reconstruye cuadros completos.
La primera vez, el Loader prepara una copia compatible de la intro con todos
sus fotogramas completos y conserva ZS3USOP.original.PSS como respaldo. Esto se
hace una sola vez y puede tardar unos segundos.

Compatibilidad y seguridad
--------------------------
La herramienta identifica las funciones por sus nombres internos, no por
direcciones fijas. Antes de iniciar comprueba que la actualización conserva
todos los símbolos y que puede resolver el payload completo. Si una versión
oficial cambia de manera incompatible, se detiene con un mensaje en vez de
parchear a ciegas.

Está preparado exclusivamente para:
  - Tenkaichi3Decomp oficial Windows x64;
  - DBZ Competitive Edition v8.4.1.

No incluye ni distribuye archivos del juego.

Correcciones de v0.5
--------------------
Además de las protecciones anteriores, valida las direcciones de los nodos de
los modelos competitivos. Si un personaje no trae un nodo usado por un efecto
de ki, se emplea la posición segura del personaje en vez de provocar un cierre.

Novedades de v0.6
-----------------
Incluye una aplicación gráfica con icono y botones para jugar, actualizar desde
GitHub e importar la memory. El ejecutable incluye sus dependencias y no exige
instalar Python.

Novedades de v0.8
-----------------
- Nueva identidad visual de Universo Tenkaichi en el icono y la ventana.
- Logo de Competitive Edition integrado en el encabezado.

Novedades de v0.9
-----------------
- Interfaz rediseñada y flujo principal simplificado.
- "Jugar Competitive" comprueba e instala actualizaciones automáticamente.
- La consulta usa metadatos de GitHub y evita descargas cuando no hay cambios.
- La importación de memory se identifica como una función offline.

Novedades de v0.10
------------------
- El primer inicio ofrece importar opcionalmente una memory de PCSX2 justo
  después de seleccionar la ISO y antes de abrir el juego.

Novedades de v0.11
------------------
- La memory instalada se replica en `net_session` para usar sus valores de
  balance en online.
- Los archivos se protegen contra la limpieza automática mientras el loader
  permanece abierto.
- Se muestra y guarda un SHA-256 para comprobar que ambos jugadores utilizan
  exactamente la misma memory competitiva.

Novedades de v0.12
------------------
- Se reserva el espacio de "Actualizar ISO + memory" para la instalación
  controlada de nuevas versiones competitivas.
- "Cambiar memory manualmente" queda como alternativa para reemplazar el
  balance después de instalar y solo se habilita si el juego está preparado.

Novedades de v0.13
------------------
- Interfaz reconstruida desde cero como centro de control con barra lateral,
  bloque principal de juego, acciones independientes y registro compacto.
- Los créditos aparecen permanentemente en una tarjeta dedicada:
  "Decomp: z3xox" y "Competitive Loader: Rising".

Novedades de v0.14
------------------
- Chat de texto durante las sesiones online: T para escribir, Enter para enviar
  y Escape para cancelar.
- Los paquetes de chat son una extensión compatible: el decomp oficial que no
  la conoce los ignora sin afectar los controles ni el rollback.
- START y el menú de pausa quedan deshabilitados únicamente mientras una sesión
  online está activa.

Novedades de v0.16
------------------
- Comprueba al iniciar si existe una Release nueva del propio loader.
- Muestra una opción visible para descargarla e instalarla.
- Verifica el paquete antes de cerrar, reemplaza únicamente el ejecutable y
  vuelve a abrir la aplicación automáticamente.
- El proyecto ya puede construirse desde cualquier ruta, sin rutas absolutas
  guardadas en el archivo de Visual Studio/PyInstaller.

Novedades de v0.17
------------------
- Añade una barrera online antes de mostrar la selección de personajes: el
  host y el invitado avanzan únicamente cuando ambos terminaron de cargar.
- Añade otra barrera después de cargar cada pelea para que el equipo más
  rápido espere al más lento antes de iniciar la simulación.
- En online omite automáticamente las intros de escenario y personajes. Así
  el final local de una voz o cámara no puede adelantar solo a un jugador.
- Las barreras se liberan en un mismo tick de red y avisan si el otro jugador
  no usa una versión compatible del loader.

Novedades de v1.0
-----------------
- Competitive Loader pasa a su primera versión estable.
- Las nuevas Releases se comprueban al abrir y se instalan desde el botón
  "Actualizar Loader", sin reemplazar ISO, memory ni configuración.
- Se elimina el modo de prueba de dos jugadores en un mismo PC.

Novedades de v1.0.1
-------------------
- El chat aparece como un cuadro con historial breve dentro del juego.
- El roster online muestra el nombre del jugador rival.
- Los límites online cambian a 180, 240, 360 y 480 segundos, manteniendo
  intacta la opción sin límite.
- La interfaz muestra versiones disponibles e instaladas del decomp y del
  Loader, con el botón de actualización junto a esa información.
- Primera prueba de compatibilidad adicional para AFS2 e intros.

Novedades de v1.0.2
-------------------
- Se corrige la causa real de la saturación en ciertos ADX del AFS2: ahora se
  respeta su marca de fin CRI antes del relleno, sin reducir el volumen.
- La intro competitiva se convierte una sola vez a un flujo MPEG compatible
  con el reproductor del decomp. El original queda respaldado y la ISO no se
  modifica.
- Durante el online se bloquean F11, mover, redimensionar, minimizar y maximizar
  la ventana para impedir congelamientos y desincronizaciones del hilo de red.

Novedades de v1.0.3
-------------------
- El actualizador consulta un repositorio público dedicado exclusivamente a las
  Releases binarias. Así puede detectar versiones sin iniciar sesión en GitHub
  mientras el repositorio del código fuente permanece privado.
- Corrige el estado "No disponible" que mostraba la versión 1.0.2 al consultar
  una Release alojada en un repositorio privado.

Novedades de v1.0.4
-------------------
- Estado previo Listo/Cargando para los dos jugadores antes del roster.
- Verificación visible de la versión del Loader y del SHA-256 de la memory.
- Marcador de la sesión que se conserva entre las revanchas nativas.
- Chat renovado con cuatro mensajes rápidos.
- El roster muestra ambos nombres, compatibilidad y marcador.

Novedades de v1.0.5
-------------------
- El botón de actualización deja explícito el flujo "Actualizar y reiniciar".
- Después de verificar el ZIP, el Loader actual se cierra, se reemplaza
  únicamente `Competitive Loader.exe` y se abre automáticamente la versión
  nueva. La ISO, memory, runtime y configuración permanecen intactos.

Novedades de v1.0.6
-------------------
- El ejecutable nuevo actúa como su propio instalador; ya no depende de un
  script temporal de PowerShell para reemplazar la versión anterior.
- Espera el cierre del Loader actual y cierra cualquier otra instancia que use
  exactamente la misma ruta antes de copiar, evitando que Windows bloquee el
  archivo.
- Comprueba el SHA-256 después del reemplazo, abre la versión nueva y elimina
  `.competitive-update` cuando el instalador termina.

Novedades de v1.0.7
-------------------
- Los mensajes rápidos pasan a F2, F3, F4 y F5.
- F1 queda libre para abrir el menú de configuración del decomp, incluso si el
  cuadro de chat estaba abierto.

Novedades de v1.0.8
-------------------
- Activa "Instalar ISO + memory" para cambiar a una ISO competitiva nueva sin
  borrar ni volver a instalar el decomp.
- La ISO nueva se extrae y valida en una carpeta temporal. Solo sustituye los
  datos actuales cuando sus firmas y el parche son compatibles; ante cualquier
  error restaura automáticamente la instalación anterior.
- Permite importar una memory nueva en el mismo flujo o conservar la actual.
- Mantiene la configuración, partidas, actualizaciones y archivos personales.

Novedades de v0.7
-----------------
El primer inicio ya no pide descargar ni seleccionar manualmente el ZIP del
decomp. El usuario proporciona únicamente la ISO competitiva y el botón Jugar
obtiene automáticamente la última versión oficial compatible desde GitHub.
Cuando la instalación ya existe, Jugar ofrece comprobar la publicación más
reciente antes de abrir; también permite continuar con la versión instalada.

Uso avanzado
------------
  python competitive_loader.py --release "oficial.zip" --iso "juego.iso"
  python competitive_loader.py --prepare-only
  python competitive_loader.py --check
  python competitive_loader.py --update-github

Para seleccionar otra actualización, borra competitive_loader.json o usa
--release con la ruta del ZIP nuevo.

Créditos
--------
Decomp: z3xox
Competitive Loader: Rising
