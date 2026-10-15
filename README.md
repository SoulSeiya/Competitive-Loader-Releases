# Competitive-Loader-Releases
Código y publicaciones de Competitive Loader.

El Loader permite preparar una instalación competitiva a partir de la ISO propia del usuario. El repositorio no incluye ISO, memory ni datos extraídos del juego.

## Pruebas online con decomp 0.1.35.2

Para jugar manualmente con el perfil nuevo, abre `bin/Competitive Loader Experimental.exe` y pulsa **Jugar Competitive · Experimental**. Usa una instalación competitiva ya preparada con el decomp 0.1.35.2 revisado. Si no encuentra una, permite seleccionar su carpeta. Conserva la importación de memory y fija la versión del decomp; no descarga actualizaciones. El chat se abre con Tab. El menú online y el reloj real usan 180, 240, 360 y 480 segundos, más sin límite; ambos jugadores necesitan esta misma versión. Los tiempos offline originales se restauran antes de cargar una pelea offline.

Construcción de esta interfaz: `python -m PyInstaller --noconfirm --distpath dist --workpath build/experimental "build_gui/Competitive Experimental.spec"`.

La interfaz experimental vuelve a convertir el vídeo de apertura competitivo a fotogramas completos de tipo I, necesarios para el decodificador actual. La primera vez conserva `ZS3USOP.original.PSS` y prepara una copia compatible; no cambia la ISO ni las reglas online. El laboratorio automatizado conserva su configuración anterior para reproducir los resultados registrados.

La interfaz también activa una corrección independiente del audio AFS2: respeta la marca de fin CRI en el reproductor físico, bajo el bloqueo del stream. No cambia los archivos, no calcula índices usando el tamaño de Player y no escribe gPortAdxView ni su duración lógica online. El objeto se regenera con `./build_audio.ps1 -Compiler RUTA_CLANG_PLUS_PLUS`. Las pruebas nativas están en `tests/test_audio_native.cpp` (compilar y ejecutar con un compilador C++ de Windows x64).

Los tiempos se regeneran con `./build_times.ps1 -Compiler RUTA_CLANG_PLUS_PLUS`. Su wrapper solo establece los cuatro valores según el estado de sesión antes de Battle_Load; no introduce barreras ni fotogramas adicionales. Las etiquetas se reemplazan únicamente si cada texto aparece una vez en el ejecutable revisado.

Esta rama incorpora un laboratorio experimental: [ONLINE-LAB.md](ONLINE-LAB.md).
Ejecuta dos runtimes independientes por loopback y conserva logs y hashes para investigar desincronizaciones.

El perfil se activa únicamente desde `local_online_test.py`. La GUI continúa usando el parche anterior; esta rama no es una actualización estable ni activa automáticamente el perfil experimental para otros usuarios.

El laboratorio conserva las reglas competitivas y prueba las implementaciones oficiales de red, chat, pausa y tiempos de voz. Deja fuera las extensiones antiguas de red/audio y utiliza los tiempos oficiales mientras se valida la base.

## Desarrollo

Python 3 en Windows x64:

```powershell
python -m unittest discover -s tests -v
```

Para construir la aplicación gráfica existente: `./build.ps1` (instala PyInstaller). Construirla no convierte el perfil de laboratorio en el perfil de la GUI.

Los objetos de `payload/` son los artefactos existentes usados por el parche. Su regeneración reproducible a partir de las modificaciones de gameplay sigue pendiente de integrar; `native/competitive_chat.cpp` contiene la extensión antigua, excluida del perfil de laboratorio.

No crear una Release estable a partir de esta rama sin completar las pruebas descritas en ONLINE-LAB.md.
