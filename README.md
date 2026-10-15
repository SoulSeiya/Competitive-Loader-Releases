# Competitive-Loader-Releases
Código y publicaciones de Competitive Loader.

El Loader permite preparar una instalación competitiva a partir de la ISO propia del usuario. El repositorio no incluye ISO, memory ni datos extraídos del juego.

## Rising Battle 1.5.0 — torneo local en validación

La entrada Tenkaichi Budokai Online abre las salas y torneos BTC. Dragon Net Battle mantiene su menú y códigos. Incluye inscripciones, FT1–FT5, bracket de 2–32 participantes, pases libres, resultados coincidentes de ambos jugadores y anuncios en el chat. La prueba Todos contra mí prepara cuatro inscritos: el usuario y tres bots con clientes reales programados; el humano juega los tres sets incluso si pierde. La vista de un combate de bots es una ventana local; el espectador remoto por replay y el servicio público de códigos cortos siguen pendientes. [Uso y límites de la prueba](RISING-BATTLE.md).

## Release 1.3.2

En F1 → Online → Host se puede elegir Sin FT o FT1–FT5 antes de conectar. El anfitrión transmite el objetivo a ambos jugadores con las reglas de la sesión privada. Gana quien alcanza esas victorias confirmadas; los empates no avanzan el FT. Al finalizar, el marcador se detiene, aparece GG con el ganador y se cierra el online de ambos. Ambos necesitan este Loader. La búsqueda rápida mantiene sus reglas.

La selección de personajes muestra el rival conectado. El botón Buscar actualizaciones permite consultar de nuevo las versiones de GitHub sin cerrar la aplicación; instalar una actualización sí reinicia el Loader.

El paquete publicable se construye con `build.ps1` y abre `competitive_release_gui.py`. Consulta las publicaciones del decomp al jugar y valida su compatibilidad antes de instalarlas. La primera versión admite el ejecutable revisado de v0.1.35.2: una publicación futura sin revisar no reemplaza la instalación actual.

Al abrir una versión nueva aparece un aviso con sus mejoras, una sola vez por versión. Durante el online se bloquean arrastre, redimensionado, menú de sistema y F11 para evitar el bucle modal de Windows; al finalizar se restaura el comportamiento de la ventana. El botón de cerrar sigue funcionando.

El marcador online muestra las victorias y empates de la sesión y se conserva entre peleas y revanchas. Solo cuenta resultados confirmados por la red y descarta observaciones que el rollback repite o corrige. Se reinicia al terminar la sesión.

Cada arranque/operación guarda una carpeta en `logs/` con `local.log`, `online.log` y `session.json`; un arranque correcto añade `patch.log`. Se captura el código de salida y el informe nativo de crash si aparece. Los logs rotan al alcanzar 10 MB (tres respaldos por archivo), permanecen en el equipo y se abren desde el botón de la interfaz. Detalles de esta versión: [RELEASE-NOTES.md](RELEASE-NOTES.md).

GitHub Actions comprueba y empaqueta `main`. Una etiqueta `vX.Y.Z` que coincida con la versión del código publica el ZIP en Releases. Las ISO, memory y configuraciones personales no se incluyen en ese paquete.

## Pruebas online con decomp 0.1.35.2

Para jugar manualmente con el perfil nuevo, abre `bin/Competitive Loader Experimental.exe` y pulsa **Jugar Competitive · Experimental**. Usa una instalación competitiva ya preparada con el decomp 0.1.35.2 revisado. Si no encuentra una, permite seleccionar su carpeta. Conserva la importación de memory y fija la versión del decomp; no descarga actualizaciones. El chat se abre con Tab. El menú online y el reloj real usan 180, 240, 360 y 480 segundos, más sin límite; ambos jugadores necesitan esta misma versión. Los tiempos offline originales se restauran antes de cargar una pelea offline.

Construcción de esta interfaz: `python -m PyInstaller --noconfirm --distpath dist --workpath build/experimental "build_gui/Competitive Experimental.spec"`.

La interfaz experimental vuelve a convertir el vídeo de apertura competitivo a fotogramas completos de tipo I, necesarios para el decodificador actual. La primera vez conserva `ZS3USOP.original.PSS` y prepara una copia compatible; no cambia la ISO ni las reglas online. El laboratorio automatizado conserva su configuración anterior para reproducir los resultados registrados.

La interfaz también activa una corrección independiente del audio AFS2: respeta la marca de fin CRI en el reproductor físico, bajo el bloqueo del stream. No cambia los archivos, no calcula índices usando el tamaño de Player y no escribe gPortAdxView ni su duración lógica online. El objeto se regenera con `./build_audio.ps1 -Compiler RUTA_CLANG_PLUS_PLUS`. Las pruebas nativas están en `tests/test_audio_native.cpp` (compilar y ejecutar con un compilador C++ de Windows x64).

Los tiempos se regeneran con `./build_times.ps1 -Compiler RUTA_CLANG_PLUS_PLUS`. Su wrapper solo establece los cuatro valores según el estado de sesión antes de Battle_Load; no introduce barreras ni fotogramas adicionales. Las etiquetas se reemplazan únicamente si cada texto aparece una vez en el ejecutable revisado.

Esta rama incorpora un laboratorio experimental: [ONLINE-LAB.md](ONLINE-LAB.md).
Ejecuta dos runtimes independientes por loopback y conserva logs y hashes para investigar desincronizaciones.

El laboratorio automatizado mantiene su perfil base para reproducir pruebas anteriores. La GUI de Release activa las correcciones de audio, tiempos y marcador; `--session-score` permite probar el marcador en el laboratorio con los tiempos oficiales.

El laboratorio conserva las reglas competitivas y prueba las implementaciones oficiales de red, chat, pausa y tiempos de voz. Deja fuera las extensiones antiguas de red/audio y utiliza los tiempos oficiales mientras se valida la base.

## Desarrollo

Python 3 en Windows x64:

```powershell
python -m unittest discover -s tests -v
```

Para construir la aplicación gráfica de Release: `./build.ps1` (instala PyInstaller).

Los objetos de `payload/` son los artefactos existentes usados por el parche. Su regeneración reproducible a partir de las modificaciones de gameplay sigue pendiente de integrar; `native/competitive_chat.cpp` contiene la extensión antigua, excluida del perfil de laboratorio.

El objeto del marcador se regenera con `./build_score.ps1 -Compiler RUTA_CLANG_PLUS_PLUS -ImGuiInclude RUTA_DECOMP/port/third_party/imgui -SdlInclude RUTA_SDL/include`, usando los headers del decomp v0.1.35.2 revisado. `tests/test_score_native.cpp` comprueba confirmación, revanchas, rollback, empates y reinicio de sesión. GitHub Actions ejecuta esta prueba nativa además de las pruebas Python. Las pruebas locales finitas no garantizan ausencia de desync en Internet.

La prueba adicional `tests/test_window_native.cpp` crea su propia ventana SDL oculta y comprueba la instalación/restauración del procedimiento de Windows, los comandos de movimiento/tamaño y F11. Compilar con C++ Windows x64, headers/biblioteca SDL3 y user32. `--release-profile` en el laboratorio usa la petición de sesión nativa desde un estado normal guardado; el perfil base conserva su arranque anterior para reproducir sus resultados.

## Hotfix 1.3.2

La traza del ataque 1 de Androide 16 llega a EftObj_Create → BtlObj_Create → BtlObjMdl_BindFiles, leyendo modelo nulo+0x6C. EftObj_Create usa size=0x20 para un modelo embebido; el comprobador competitivo trataba ese valor fijo como longitud del archivo y devolvía una entrada vacía. La nueva extensión recupera un límite de lectura dentro de la asignación activa que contiene el modelo antes de delegar al constructor original. No sustituye la entrada vacía por un efecto arbitrario ni desactiva los límites de los archivos normales.

Se regenera con `./build_effect_model.ps1 -Compiler RUTA_CLANG_PLUS_PLUS`. La prueba nativa `tests/test_effect_model_native.cpp` reproduce el modelo vacío y verifica el tamaño recuperado, datos truncados, memoria liberada y recursos ordinarios. El 15 de octubre de 2026 el usuario repitió el ataque 1 de Androide 16 con el Loader 1.3.2 y confirmó que funcionó sin el cierre reportado.
