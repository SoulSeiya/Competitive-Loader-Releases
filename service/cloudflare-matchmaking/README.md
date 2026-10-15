# Matchmaking propio BTC en Cloudflare — desplegado

El ejecutable revisado ya admite `BT3_MATCH_URL`. No hay que cambiar el protocolo
de pelea: se despliega el Worker de upstream en una cuenta propia y se configura
su URL en **Configurar matchmaking BTC (Worker)** del Loader.

La versión 1.5.2 usa por defecto https://btc-matchmaking.paulogomez41.workers.dev
en todas las instancias, incluidos bots. Puedes cambiarla desde el Loader. Guardar
el campo vacío desactiva explícitamente los códigos y fija loopback; nunca se usa
la URL oficial integrada. Offline y conexión por IP siguen disponibles.
La versión anterior 1.5.1 aún usaba el servicio oficial para enlazar las peleas.

## Preparado localmente

Desde la raíz, `python tools/prepare_matchmaking.py` descarga Worker, esquema,
pruebas, documentación y licencia del commit upstream fijado en el script. Los
archivos quedan en `upstream/`, excluidos de Git, con manifiesto de hashes. Se
mantienen sus avisos y fuente. El script solo descarga: no configura ni despliega
recursos de ninguna cuenta. Para comprobar el Worker sin red:

```powershell
node tools/test_matchmaking.mjs
```

## Reproducir el despliegue en otra cuenta

1. Crear una cuenta Cloudflare y entrar a su panel.
2. Crear una base D1 llamada `btc-matchmaking-rooms`; ejecutar las dos sentencias
   de `upstream/schema.sql` en su consola, una por una.
3. Crear un Worker `btc-matchmaking`, pegar `upstream/worker.js`, vincular la base
   como **DB** y desplegarlo.
4. Usar su URL HTTPS de workers.dev en el botón de configuración del Loader.
   Ambos jugadores deben usar la misma URL. No se necesita un dominio comprado.
5. Probar Host/Join y una pelea entre dos equipos antes de publicar la release.

`wrangler.example.toml` es una plantilla alternativa para CLI: requiere el ID de
la base creada y autenticación del usuario. No contiene los identificadores privados de la cuenta usada para el despliegue.
No configures `BUILD_KEYS` con las claves del decomp: en un servicio propio pueden
omitirse inicialmente. Si se habilita verificación de builds, requiere claves
propias y una compilación BTC que las firme; aún no se ha implementado esa firma.

El relay TURN es opcional. Sin configurarlo, algunas parejas con NAT restrictivo
podrían no conectar. No se han creado claves TURN ni cambiado el plan gratuito; su
configuración y límites deben revisarse antes de activarlo. Workers y D1 tienen
planes gratuitos con cuotas, no recursos ilimitados.

## Separación de servicios

Este Worker genera códigos **de combate para dos jugadores**. El coordinador
`rising_service.py` mantiene **la sala de torneo, usuarios, bracket y chat**. Su
protocolo es distinto y el servidor Python no se puede pegar como un Worker JS.
La sala de torneo todavía requiere alojamiento propio o una adaptación posterior
a Workers/Durable Objects. Cambiar `BT3_MATCH_URL` por sí solo no publica esa sala.

Documentación de referencia:
- https://github.com/z3xox/Tenkaichi3Decomp/tree/main/port/matchmaking
- https://developers.cloudflare.com/workers/platform/pricing/
- https://developers.cloudflare.com/realtime/turn/


## Despliegue actual, 15 de octubre de 2026

El Worker btc-matchmaking está publicado en la cuenta del usuario, con la base D1
btc-matchmaking-rooms vinculada como DB. Las tablas rooms y used están creadas.
MIN_RELEASE y LATEST_RELEASE valen 135. No hay BUILD_KEYS ni credenciales TURN.

Pasaron hello, Host, Join y consulta recíproca de peers por HTTPS. Dos instancias
reales del ejecutable revisado también conectaron entre sí usando este Worker;
se comprobó la URL aplicada en los dos logs. Esa comprobación no completó un FT
ni valida aún conexiones entre dos redes distintas.
