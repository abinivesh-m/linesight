"""Run the shop-floor simulator: three Modbus TCP machines on localhost.

    python -m linesight.sim --hours 8

Each machine publishes the same nine points a PLC would: three coils and five
holding registers. Nothing else is exposed, so the collector cannot cheat.

The simulator also watches the `commands` table, which is how the Settings page
injects a fault for a demo. That control path writes to the PLC, never to the
database the dashboard reads - the classifier still has to work it out.
"""

from __future__ import annotations

import argparse
import asyncio
import time

from . import db
from .config import MACHINES as DEFAULT_MACHINES, Machine
from .modbus_server import ModbusTcpServer
from .model import MachineModel


def _rig_machines(conn) -> tuple[Machine, ...]:
    rows = db.machines_enabled(conn)
    if not rows:
        return DEFAULT_MACHINES
    return tuple(
        Machine(r["id"], r["name"], r["host"], int(r["port"]), int(r["unit"]), int(r["ideal_cycle_ms"]))
        for r in rows
    )


async def run(hours: float, seed: int) -> None:
    conn = db.init()
    machines = _rig_machines(conn)

    now = time.time()
    rig: dict[str, tuple[MachineModel, list[int], list[int]]] = {}
    servers: list[ModbusTcpServer] = []

    for index, machine in enumerate(machines):
        model = MachineModel(machine, seed + index, now, hours * 3600)
        coils = [0] * 8
        registers = [0] * 8
        server = ModbusTcpServer(machine.host, machine.port, machine.unit, coils, registers)
        await server.start()
        servers.append(server)
        rig[machine.id] = (model, coils, registers)
        print(f"  {machine.id:9} {machine.name:16} modbus tcp {machine.host}:{machine.port} unit {machine.unit}")

    print(f"\n{len(servers)} machines up. Ctrl+C to stop.\n")
    next_command_check = 0.0

    try:
        while True:
            now = time.time()

            if now >= next_command_check:
                for command in db.pending_commands(conn):
                    entry = rig.get(command["machine"])
                    if entry is not None:
                        entry[0].force(command["kind"], float(command["seconds"]), now)
                        print(f"  injected {command['kind']} on {command['machine']} for {command['seconds']:.0f}s")
                    db.complete_command(conn, command["id"])
                conn.commit()
                next_command_check = now + 1.0

            for machine in machines:
                model, coils, registers = rig[machine.id]
                fresh_coils, fresh_registers = model.at(now)
                coils[:] = fresh_coils
                registers[:] = fresh_registers
            await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        pass
    finally:
        for server in servers:
            await server.stop()
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="LineSight Modbus TCP simulator")
    parser.add_argument("--hours", type=float, default=8.0)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    try:
        asyncio.run(run(args.hours, args.seed))
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
