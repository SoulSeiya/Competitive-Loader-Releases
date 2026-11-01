# Rising Battle — Cliente BTC Competitive Edition

Versión 2.0.1 para Windows x64. Salas casuales, amigos, chat, duelos FT y ranked provisional.

El motor BTC 0.1.38.1 está incluido y permanece fijo. Instala tus propios datos desde una ISO competitiva y una memory compatible. El repositorio y los paquetes no distribuyen datos de disco, memory, perfiles ni credenciales.

Diagnósticos de desync activados por defecto, desactivables desde Ajustes → Diagnósticos. El mismo menú permite enviar resúmenes técnicos de los registros anteriores, previa confirmación local. Solo el equipo autorizado puede leer esos informes en su panel privado. Retención visible: 14 días, con limpieza programada.

Consulta RELEASE-NOTES.md para instalación, límites y cambios. El personaje y la técnica todavía no se capturan en los informes.

Para construir: instala requirements-build.txt y ejecuta python -m PyInstaller --noconfirm --distpath dist-web --workpath build-web "build_gui/Competitive Web Client.spec". Los módulos nuevos no añaden dependencias de red externas.
