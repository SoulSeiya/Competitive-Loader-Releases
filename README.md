# Competitive-Loader-Releases
Código y publicaciones de Competitive Loader.

El Loader permite preparar una instalación competitiva a partir de la ISO propia del usuario. El repositorio no incluye ISO, memory ni datos extraídos del juego.

## Pruebas online con decomp 0.1.35.2

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
