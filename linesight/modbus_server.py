"""A minimal Modbus TCP server, written against the wire format.

pymodbus 3.16 ships a simulator datastore, but it does not reflect runtime
writes in this build (holding-register reads fail with illegal-data-address
before a value is ever set). The listener below implements the parts of the
protocol a PLC and our collector actually use, so `linesight.sim` is a real
Modbus TCP endpoint rather than a lookalike:

    FC 1  read coils            FC 5  write single coil
    FC 3  read holding regs     FC 6  write single register
    FC 15 write multiple coils  FC 16 write multiple registers

The collector talks to it with pymodbus. If it ever stops speaking the wire
format, the collector breaks - which is the point.
"""

from __future__ import annotations

import asyncio
import struct

ILLEGAL_FUNCTION = 0x01
ILLEGAL_ADDRESS = 0x02
ILLEGAL_VALUE = 0x03


class ModbusTcpServer:
    """One unit, one coil table, one holding-register table."""

    def __init__(self, host: str, port: int, unit: int, coils: list[int], registers: list[int]) -> None:
        self.host = host
        self.port = port
        self.unit = unit
        self.coils = coils
        self.registers = registers
        self._server: asyncio.AbstractServer | None = None
        self.requests = 0

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, self.host, self.port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    # ---------------------------------------------------------------- wire
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                header = await reader.readexactly(7)
                tid, pid, length, uid = struct.unpack(">HHHB", header)
                if pid != 0 or length < 2:
                    return
                pdu = await reader.readexactly(length - 1)
                self.requests += 1
                response = self._process(uid, pdu)
                writer.write(struct.pack(">HHHB", tid, 0, len(response) + 1, uid) + response)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            return
        finally:
            try:
                writer.close()
            except Exception:  # noqa: BLE001 - a closed socket is not an error
                pass

    def _process(self, uid: int, pdu: bytes) -> bytes:
        fc = pdu[0]
        if uid not in (0, self.unit):
            return bytes([fc | 0x80, ILLEGAL_ADDRESS])

        if fc == 1:
            return self._read_bits(pdu, self.coils)
        if fc == 3:
            return self._read_registers(pdu, self.registers)
        if fc == 5:
            return self._write_coil(pdu)
        if fc == 6:
            return self._write_register(pdu)
        if fc == 15:
            return self._write_coils(pdu)
        if fc == 16:
            return self._write_registers(pdu)
        return bytes([fc | 0x80, ILLEGAL_FUNCTION])

    def _read_bits(self, pdu: bytes, table: list[int]) -> bytes:
        address, quantity = struct.unpack(">HH", pdu[1:5])
        if not 1 <= quantity <= 2000 or address + quantity > len(table):
            return bytes([pdu[0] | 0x80, ILLEGAL_ADDRESS])
        byte_count = (quantity + 7) // 8
        payload = bytearray(byte_count)
        for i in range(quantity):
            if table[address + i]:
                payload[i // 8] |= 1 << (i % 8)
        return bytes([pdu[0], byte_count]) + bytes(payload)

    def _read_registers(self, pdu: bytes, table: list[int]) -> bytes:
        address, quantity = struct.unpack(">HH", pdu[1:5])
        if not 1 <= quantity <= 125 or address + quantity > len(table):
            return bytes([pdu[0] | 0x80, ILLEGAL_ADDRESS])
        values = struct.pack(f">{quantity}H", *[int(v) & 0xFFFF for v in table[address:address + quantity]])
        return bytes([pdu[0], quantity * 2]) + values

    def _write_coil(self, pdu: bytes) -> bytes:
        address, value = struct.unpack(">HH", pdu[1:5])
        if address >= len(self.coils):
            return bytes([pdu[0] | 0x80, ILLEGAL_ADDRESS])
        if value not in (0x0000, 0xFF00):
            return bytes([pdu[0] | 0x80, ILLEGAL_VALUE])
        self.coils[address] = 1 if value == 0xFF00 else 0
        return pdu[:5]

    def _write_register(self, pdu: bytes) -> bytes:
        address, value = struct.unpack(">HH", pdu[1:5])
        if address >= len(self.registers):
            return bytes([pdu[0] | 0x80, ILLEGAL_ADDRESS])
        self.registers[address] = value
        return pdu[:5]

    def _write_coils(self, pdu: bytes) -> bytes:
        address, quantity, byte_count = struct.unpack(">HHB", pdu[1:6])
        if not 1 <= quantity <= 1968 or address + quantity > len(self.coils):
            return bytes([pdu[0] | 0x80, ILLEGAL_ADDRESS])
        if byte_count != (quantity + 7) // 8 or len(pdu) < 6 + byte_count:
            return bytes([pdu[0] | 0x80, ILLEGAL_VALUE])
        payload = pdu[6:6 + byte_count]
        for i in range(quantity):
            self.coils[address + i] = (payload[i // 8] >> (i % 8)) & 1
        return pdu[:5]

    def _write_registers(self, pdu: bytes) -> bytes:
        address, quantity, byte_count = struct.unpack(">HHB", pdu[1:6])
        if not 1 <= quantity <= 123 or address + quantity > len(self.registers):
            return bytes([pdu[0] | 0x80, ILLEGAL_ADDRESS])
        if byte_count != quantity * 2 or len(pdu) < 6 + byte_count:
            return bytes([pdu[0] | 0x80, ILLEGAL_VALUE])
        values = struct.unpack(f">{quantity}H", pdu[6:6 + byte_count])
        for i, value in enumerate(values):
            self.registers[address + i] = value
        return pdu[:5]
