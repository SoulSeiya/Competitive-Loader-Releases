"""Explicit native Worker selection; never falls back to the upstream service."""
import urllib.parse

LOCAL_MATCHMAKING = "http://127.0.0.1:8787"
DEFAULT_MATCHMAKING = "https://btc-matchmaking.paulogomez41.workers.dev"


def validate_url(value):
    if not isinstance(value, str):
        raise ValueError("Escribe la URL de tu Worker de matchmaking BTC")
    value=value.strip().rstrip("/")
    if not value:
        return ""
    if any(ord(c)<=32 or ord(c)==127 for c in value):
        raise ValueError("La URL no puede contener espacios ni caracteres de control")
    parsed=urllib.parse.urlsplit(value)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path or parsed.scheme not in ("http","https")):
        raise ValueError("Usa la URL base del Worker, sin ruta, parámetros ni credenciales")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Puerto de matchmaking inválido")
    host=parsed.hostname.lower()
    if host=="bt3decomp.workers.dev" or host.endswith(".bt3decomp.workers.dev"):
        raise ValueError("Usa tu Worker BTC; el servicio oficial del decomp no se usa en este Loader")
    if parsed.scheme!="https" and host not in ("127.0.0.1","localhost","::1"):
        raise ValueError("El matchmaking remoto requiere HTTPS")
    return value


def environment(config, overrides=None):
    supplied=(overrides or {}).get("BT3_MATCH_URL")
    value=validate_url(supplied if supplied is not None else config.get("btc_matchmaking_url", DEFAULT_MATCHMAKING))
    # Nonempty local URL overrides the executable's built-in upstream URL.
    return {"BT3_MATCH_URL":value or LOCAL_MATCHMAKING,
            "BTC_MATCH_UNCONFIGURED":None if value else "1"}
