# Competitive Loader

Loader publico para jugar Competitive Edition con Tenkaichi3Decomp. Compatible con **0.1.35.4** y **0.1.35.2**.

[Descargar la ultima version](https://github.com/SoulSeiya/Competitive-Loader-Releases/releases/latest)

## Funciones de juego

- Dragon Net Battle original: Host, Quick match, Join y codigos para partidas de dos jugadores.
- FT1 a FT5, marcador persistente, rival conectado y GG al terminar el set.
- Tiempos BTC de 180, 240, 360 y 480 segundos, mas sin limite.
- Correcciones de intro, audio y modelos de efectos.
- Chat original con Tab y bloqueo de movimiento de ventana durante el online.
- Logs locales y online para investigar crashes y desincronizaciones.
- Busqueda de actualizaciones con cache y alternativa publica cuando GitHub limita su API.

## Instalacion

Extrae el ZIP y abre `Competitive Loader.exe`. Necesitas tu propia ISO competitiva y memory compatible. Ambos jugadores deben usar las mismas versiones y datos. Conserva `CompetitiveRuntime` y `competitive_loader.json` al actualizar.

El repositorio y el paquete no incluyen ISO, memory ni datos extraidos del juego.
Las salas, torneos, bots y espectadores experimentales se mantienen fuera de la distribucion y del codigo actual de main.

## Desarrollo y comprobaciones

`build.ps1` construye el paquete y verifica que no contenga modulos ni parches experimentales. GitHub Actions ejecuta las pruebas y el empaquetado en main. Las Releases se publican desde versiones verificadas.

- [Funciones e instalacion](README.txt)
- [Notas de version](RELEASE-NOTES.md)
- [Revision de compatibilidad del decomp](docs/decomp-0.1.35.4.md)
- [Matchmaking propio de dos jugadores](service/cloudflare-matchmaking/README.md)

Los ensayos locales no sustituyen las partidas prolongadas entre equipos reales.
