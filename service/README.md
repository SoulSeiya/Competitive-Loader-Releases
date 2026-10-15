# Servicio de salas BTC

Coordinador propio, independiente del servicio oficial del decomp. Genera códigos
BTC-XXXXXX y mantiene hasta 32 usuarios por sala, chat y el torneo completo. Todos
los clientes conocen la URL del mismo servicio y hacen peticiones salientes; no
necesitan exponer un puerto de sala en su equipo. Las peleas siguen usando el
matchmaking nativo de dos jugadores. No transmite ISO, memory, vídeo ni inputs.

## Prueba local

En Dragon Net Battle → Torneos BTC, pulsa **Iniciar servicio local de prueba** en
un Loader. Usa `http://127.0.0.1:7010` en los Loaders de este equipo. Crea una sala,
copia BTC-XXXXXX y entra desde los otros clientes. Cerrar el Loader que inició el
servicio local termina ese servicio y sus salas.

También se puede ejecutar separado:

```powershell
python rising_service.py --bind 127.0.0.1 --port 7010
# O con el ejecutable empaquetado:
& '.\Competitive Loader.exe' --room-service --bind 127.0.0.1 --port 7010
```

## Alojamiento público pendiente

El servidor es un proceso Python sin dependencias adicionales. Para un contenedor,
desde la raíz del repositorio:

```sh
docker build -f service/Dockerfile -t btc-rooms .
docker run --rm -p 127.0.0.1:7010:7010 btc-rooms
```

Un proxy HTTPS público debe reenviar POST `/v1/rooms` a ese puerto. Configura su URL
base en los clientes; el cliente rechaza HTTP fuera de loopback. El servidor aún
no está desplegado: no hay URL pública ni cuenta de alojamiento configurada. No
se ha probado tráfico entre equipos por Internet. El Dockerfile es una receta
preparada, no una imagen publicada ni una construcción validada en este equipo.

El prototipo guarda estado en memoria, limita la cantidad de salas y los intentos
de admisión por IP y rechaza cuerpos mayores de 4096 bytes. No registra tokens ni
mensajes. Un reinicio elimina las salas. El anfitrión debe renovar su presencia
antes de 30 segundos; su salida o caducidad cierra su sala. Antes de ofrecerlo como
servicio público estable hay que validar carga, operación y recuperación. El código
invita a entrar; cada miembro recibe un token propio y solo el token del anfitrión
autoriza expulsiones o administración del torneo.
