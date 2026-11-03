# Rising Battle — Cliente BTC Competitive Edition

Versión 2.1.0 para Windows x64. Salas casuales, amigos, chat, duelos FT y ranked provisional.

El motor BTC 0.1.38.1 está incluido y permanece fijo. Instala tus propios datos desde una ISO competitiva y una memory compatible. Los paquetes no distribuyen datos de disco, memory, perfiles, credenciales ni registros personales.

Diagnósticos de desync activados por defecto, desactivables desde Ajustes → Diagnósticos. Se capturan jugadores verificados por el servicio, personajes activos, número de traje, escenario y acciones/habilidades observadas. El envío filtra el contenido: no sube los TXT completos. Solo el administrador autorizado puede leer los informes; retención de 14 días.

Ranked FT2 / 360 segundos / 2 personajes. Ambos clientes 2.1 pueden acordar continuar tras un desync coincidente, con el último marcador confirmado por ambos. Elo normal y bono separado de juego limpio (+10/+3) al completar el FT reanudado. La reanudación necesita el servicio 2.1 activo.

Las nuevas versiones del Loader se descargan y verifican en segundo plano. El botón principal ofrece actualizar: pulsa con el juego cerrado y sin búsqueda o ranked activa. No actualiza el motor automáticamente. Los launchers anteriores conservan su interfaz de actualización hasta instalar esta versión.

Start permite saltar las intros y queda bloqueado en combate entre jugadores; contra CPU mantiene pausa. La selección conserva Personalizado 1/2/3 y bloquea Normal.

Consulta RELEASE-NOTES.md para cambios y límites de validación. Los metadatos y la última acción registrada no prueban por sí solos la causa de un desync.

Construcción pública: instala requirements-build.txt y ejecuta python -m PyInstaller --noconfirm --distpath dist-web --workpath build-web "build_gui/Competitive Web Client.spec".

La edición privada de administrador añade Reportes y una ventana integrada para el panel remoto protegido por Cloudflare Access. No incorpora secretos. Se distribuye por separado y no se reemplaza mediante el actualizador público.
