# Laboratorio separado: replay P1/P2, 1.5.4

El paquete normal no ofrece los botones de bots, simulación ni laboratorio.
La prueba local del espectador se prepara aparte y no publica una Release.

## Repetir la prueba en el equipo de desarrollo

Con el runtime instalado y el payload compilado:

```powershell
python tools/replay_spectator_lab.py --runtime RUTA_RUNTIME --seconds 15
```

El script graba entradas de una pelea CPU/CPU en un proceso propio sin ventana,
con configuración Versus. Captura ambas pistas al alcanzar el umbral y termina
solo su proceso de grabación. Después abre un proceso de replay aislado con las
dos cámaras del multijugador local. No hay dos simulaciones ni captura de vídeo.

El formato nativo tiene 0x1AC00 bytes: cabecera 0x38, bloque 0x1ABA8 y padding final
0x20. Se comprueban magic/version y las dos cuentas de entradas (1–9000). La copia
para visualizar solo cambia screenMode a 1; las pistas no se modifican. La cámara
ignora la selección única del replay durante combate normal y utiliza las vistas
izquierda/derecha nativas. Las cámaras cinematográficas conservan su vista propia.
El HUD arranca en el modo de replay con indicadores visibles; el visor nativo
conserva sus controles. Al agotar el clip, cierra su ventana para salir.

Para abrir un replay existente con el ejecutable empaquetado:

```powershell
& '.\Competitive Loader.exe' --watch-replay '.\cpu-vs-cpu.bin'
```

La configuración junto al EXE debe apuntar al runtime local. Cada reproducción
crea una copia aislada del ejecutable y save en logs/replay-spectator y usa los
assets locales por BT3_DATA. No modifica el runtime fuente. Los replay de prueba,
las capturas, logs y rutas privadas no se suben al repositorio ni al paquete normal.

## Alcance

Esto verifica la reproducción local y la presentación de dos perspectivas. No
recibe entradas de una pelea online, no implementa late join, no distribuye una
snapshot inicial ni conecta automáticamente a los espectadores del bracket. El
siguiente paso será capturar entradas confirmadas y estado inicial del combate,
distribuirlos a observadores y comprobar su simulación sin alterar a los jugadores.

## Prueba vigente de cuatro participantes (1.5.5)

El usuario sustituyó el ensayo de tres por dos humanos y dos bots reales.
El host abre el controlador con --four-player-room-test-host y pulsa Iniciar.
El coordinador de ese proceso crea salas de cuatro, prepara dos bots locales e
inscribe a los dos humanos. No modifica el coordinador normal. Al iniciar fuerza
los cruces humano/bot y una final humana, aun si perdieron las semifinales: es
un circuito de prueba anunciado en el chat, no eliminación competitiva normal.
FT1 y tiempo negociado 0, aplicado al índice real 1 de la tabla (180 segundos).

El túnel lo inicia el usuario; el proceso cloudflared se mantiene separado del
paquete invitado. Véase service/PRUEBA-CON-AMIGOS.txt. No incluye espectador online.
