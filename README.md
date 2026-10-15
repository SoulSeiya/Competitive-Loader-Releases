# Competitive-Loader-Releases
Código y publicaciones de Competitive Loader.

El Loader permite preparar una instalación competitiva a partir de la ISO propia del usuario. El repositorio no incluye ISO, memory ni datos extraídos del juego.

## Pruebas online con decomp 0.1.35.2

Para jugar manualmente con el perfil nuevo, abre `bin/Competitive Loader Experimental.exe` y pulsa **Jugar Competitive · Experimental**. Usa una instalación competitiva ya preparada con el decomp 0.1.35.2 revisado. Si no encuentra una, permite seleccionar su carpeta. Conserva la importación de memory y fija la versión del decomp; no descarga actualizaciones. El chat se abre con Tab y se mantienen los tiempos oficiales mientras se valida el perfil.

Construcción de esta interfaz: `python -m PyInstaller --noconfirm --distpath dist --workpath build/experimental "build_gui/Competitive Experimental.spec"`.

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
