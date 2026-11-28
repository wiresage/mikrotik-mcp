"""Multi-device smoke test (issue #44).

Drives the MCP server over the real stdio protocol against the two RouterOS
containers from routeros-docker/docker-compose.yml and proves that a tool call
lands on the device named by the `device` argument.

    docker-compose -f routeros-docker/docker-compose.yml up -d
    python tests/smoke_multi_device.py

Every check is self-establishing: nothing here depends on state left behind by
earlier runs. Fresh containers boot with the same identity, and the NIC of
both routers carries QEMU's MAC 52:54:00:12:34:56, so neither tells the two
apart: the checks that need to know which router answered look for the VLAN
this test created on each of them.

A lab on other host ports (the compose file's SSH_PORT_A / SSH_PORT_B) is
reached by setting the same two variables here.
"""

import asyncio
import json
import os
import re
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Matches the compose file: routeros-a -> 2222, routeros-b -> 2223, or what
# SSH_PORT_A / SSH_PORT_B say there (an "address:port" binding works too).
PORT_A = int(os.environ.get("SSH_PORT_A", "2222").rsplit(":", 1)[-1])
PORT_B = int(os.environ.get("SSH_PORT_B", "2223").rsplit(":", 1)[-1])
#
# No password is ever written to disk (CodeQL: clear-text storage). The
# default lab password is empty, which is also DeviceConfig's default, so the
# file simply omits the field. A non-empty ROUTEROS_PASS is delivered through
# the inline MIKROTIK_INVENTORY environment variable instead of the file.
PASSWORD = os.environ.get("ROUTEROS_PASS", "")

DEVICES = [
    {"title": "RouterA", "host": "127.0.0.1", "port": PORT_A, "username": "admin",
     "tags": ["lab", "primary"], "region": "NL"},
    {"title": "RouterB", "host": "127.0.0.1", "port": PORT_B, "username": "admin",
     "tags": ["lab", "secondary"], "region": "DE"},
]

INVENTORY_YAML = "".join(
    f"- title: {d['title']}\n"
    f"  host: {d['host']}\n"
    f"  port: {d['port']}\n"
    f"  username: {d['username']}\n"
    f"  tags: [{', '.join(d['tags'])}]\n"
    f"  region: {d['region']}\n"
    for d in DEVICES
)

results = []


def check(label, ok, detail=""):
    results.append((label, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if detail:
        print("        " + str(detail).replace("\n", " ")[:160])


def env(inventory_file):
    e = dict(os.environ)
    e.pop("MIKROTIK_INVENTORY", None)
    e.update({
        "MIKROTIK_INVENTORY_FILE": inventory_file,
        "MIKROTIK_MCP__TRANSPORT": "stdio",
        "PYTHONPATH": os.path.join(REPO, "src"),
    })
    if PASSWORD:
        # Inline inventory wins over the file, so a real password rides the
        # environment (never the filesystem).
        e["MIKROTIK_INVENTORY"] = json.dumps(
            [{**d, "password": PASSWORD} for d in DEVICES]
        )
    return e


def txt(res):
    return "\n".join(getattr(c, "text", "") for c in res.content)


def macs(list_interfaces_output):
    """Map interface name -> MAC from a list_interfaces response."""
    return dict(re.findall(
        r"(\S+)\s+\S+\s+\d+\s+([0-9A-Fa-f:]{17})", list_interfaces_output
    ))


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        inv_path = os.path.join(tmp, "inventory.yaml")
        with open(inv_path, "w", encoding="utf-8") as fh:
            fh.write(INVENTORY_YAML)

        params = StdioServerParameters(
            command=sys.executable, args=["-m", "mcp_mikrotik.server"],
            env=env(inv_path), cwd=REPO,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as s:
                await s.initialize()

                tools = (await s.list_tools()).tools
                names = [t.name for t in tools]
                check(f"server exposes {len(tools)} tools incl. list_devices",
                      "list_devices" in names)

                sample = [t for t in tools if t.name == "list_interfaces"][0]
                check("tools advertise a `device` argument",
                      "device" in (sample.input_schema.get("properties") or {}))

                # ── Tool D (inventory loaded from the YAML file) ──────────
                out = txt(await s.call_tool("list_devices", {}))
                check("YAML inventory loaded: list_devices shows both devices",
                      "RouterA" in out and "RouterB" in out, out)
                check("list_devices leaks no credentials",
                      "password" not in out.lower(), out)

                # ── Reach both boxes ──────────────────────────────────────
                a = txt(await s.call_tool("list_interfaces", {"device": "RouterA"}))
                b = txt(await s.call_tool("list_interfaces", {"device": "RouterB"}))
                check("command routed to RouterA", "Error" not in a[:20], a)
                check("command routed to RouterB", "Error" not in b[:20], b)

                macs_a, macs_b = macs(a), macs(b)
                parent_a = sorted(n for n in macs_a if n.startswith("ether"))[-1]
                parent_b = sorted(n for n in macs_b if n.startswith("ether"))[-1]

                # ── Write isolation: a VLAN per router, then cross-check ──
                out = txt(await s.call_tool("create_vlan_interface", {
                    "device": "RouterA", "name": "smoke-vlan-a", "vlan_id": 210,
                    "interface": parent_a, "comment": "smoke test"}))
                check("VLAN created on RouterA", "successfully" in out, out)
                out = txt(await s.call_tool("create_vlan_interface", {
                    "device": "RouterB", "name": "smoke-vlan-b", "vlan_id": 220,
                    "interface": parent_b, "comment": "smoke test"}))
                check("VLAN created on RouterB", "successfully" in out, out)

                va = txt(await s.call_tool("list_vlan_interfaces", {"device": "RouterA"}))
                vb = txt(await s.call_tool("list_vlan_interfaces", {"device": "RouterB"}))
                check("RouterA has only its own VLAN",
                      "smoke-vlan-a" in va and "smoke-vlan-b" not in va, va)
                check("RouterB has only its own VLAN",
                      "smoke-vlan-b" in vb and "smoke-vlan-a" not in vb, vb)

                # ── Selection rules ───────────────────────────────────────
                out = txt(await s.call_tool("list_interfaces", {}))
                check("omitting device with >1 device errors and lists choices",
                      "RouterA" in out and "RouterB" in out and "Error" in out, out)

                out = txt(await s.call_tool("list_interfaces", {"device": "Ghost"}))
                check("unknown device errors and lists choices",
                      "Unknown device" in out and "RouterA" in out, out)

                out = txt(await s.call_tool("list_interfaces", {"device": "routera"}))
                check("device matching is case-insensitive",
                      "Error" not in out[:20], out)

                # ── Concurrency: interleaved calls must not cross-talk ────
                # The VLAN created above tells which router answered: nothing
                # else differs between two fresh lab routers.
                def answered_by(output):
                    a_seen, b_seen = "smoke-vlan-a" in output, "smoke-vlan-b" in output
                    if a_seen != b_seen:
                        return "RouterA" if a_seen else "RouterB"
                    return None

                targets = ["RouterA", "RouterB"] * 6
                outs = [txt(o) for o in await asyncio.gather(
                    *[s.call_tool("list_interfaces", {"device": d})
                      for d in targets]
                )]
                got = [answered_by(o) for o in outs]
                check(f"{len(targets)} concurrent calls each reached the right router",
                      got == targets, f"want {targets[:4]}... got {got[:4]}...")
                check("no concurrent call errored",
                      not any("Error" in o for o in outs),
                      next((o for o in outs if "Error" in o), ""))

                serial = [txt(await s.call_tool(
                    "list_interfaces", {"device": "RouterA"}))
                    for _ in range(10)]
                check("10 back-to-back commands all succeed (no session exhaustion)",
                      all(answered_by(o) == "RouterA" for o in serial),
                      next((o for o in serial if answered_by(o) != "RouterA"), ""))

                # ── Cleanup (also exercises remove + routing) ─────────────
                out = txt(await s.call_tool("remove_vlan_interface",
                                            {"device": "RouterA", "name": "smoke-vlan-a"}))
                check("VLAN removed from RouterA", "successfully" in out, out)
                out = txt(await s.call_tool("remove_vlan_interface",
                                            {"device": "RouterB", "name": "smoke-vlan-b"}))
                check("VLAN removed from RouterB", "successfully" in out, out)
                va = txt(await s.call_tool("list_vlan_interfaces", {"device": "RouterA"}))
                vb = txt(await s.call_tool("list_vlan_interfaces", {"device": "RouterB"}))
                check("both routers back to baseline",
                      "smoke-vlan" not in va and "smoke-vlan" not in vb)

    print()
    passed = sum(1 for _, ok in results if ok)
    print(f"RESULT: {passed}/{len(results)} smoke checks passed")
    if passed != len(results):
        print("FAILED:", [l for l, ok in results if not ok])
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
