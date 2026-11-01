"""Single-paste invitation: address, TCP port and room key. No public directory/relay."""
import base64
import binascii
import ipaddress
import struct
import zlib
from rising_room import RoomClient, RoomError


def make_invite(address, port, key):
    RoomClient(address, port)  # Same restricted host grammar as the network client.
    try:
        secret = base64.urlsafe_b64decode(key + "=" * (-len(key) % 4))
        if len(secret) != 12:
            raise ValueError()
        try:
            host = b"\x04" + ipaddress.IPv4Address(address).packed
        except ipaddress.AddressValueError:
            raw = address.encode("ascii")
            if len(raw) > 128:
                raise ValueError()
            host = b"\x00" + bytes([len(raw)]) + raw
        payload = host + struct.pack("!H", port) + secret
        payload += struct.pack("!I", zlib.crc32(payload))
        return "BTC1-" + base64.b32encode(payload).decode("ascii").rstrip("=")
    except (ValueError, TypeError, UnicodeError, binascii.Error):
        raise RoomError("No se pudo generar el código de sala") from None


def read_invite(code):
    try:
        code = code.strip().upper()
        if not code.startswith("BTC1-") or len(code) > 300:
            raise ValueError()
        raw = code[5:]
        data = base64.b32decode(raw + "=" * (-len(raw) % 8))
        payload, check = data[:-4], data[-4:]
        if len(payload) < 16 or check != struct.pack("!I", zlib.crc32(payload)):
            raise ValueError()
        if payload[0] == 4:
            address, end = str(ipaddress.IPv4Address(payload[1:5])), 5
        elif payload[0] == 0:
            end = 2 + payload[1]
            address = payload[2:end].decode("ascii")
        else:
            raise ValueError()
        if len(payload) != end + 14:
            raise ValueError()
        port = struct.unpack("!H", payload[end:end + 2])[0]
        key = base64.urlsafe_b64encode(payload[end + 2:]).decode("ascii").rstrip("=")
        RoomClient(address, port)
        return address, port, key
    except (ValueError, TypeError, IndexError, UnicodeError, binascii.Error, RoomError):
        raise RoomError("Código de sala inválido o incompleto") from None
