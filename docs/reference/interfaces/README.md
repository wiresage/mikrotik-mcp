# Interfaces

`/interface`: the tools that work on any interface type, plus VLAN, bridge, WireGuard, Wi-Fi/wireless and PoE.
Source: [`src/mcp_mikrotik/scope/interfaces/`](../../../src/mcp_mikrotik/scope/interfaces/).

| Module | What it covers | Reference |
|---|---|---|
| `generic` | List, get, enable and disable an interface of any type | [Interfaces](generic.md) |
| `vlan` | VLAN interfaces (`/interface vlan`) | [VLAN](vlan.md) |
| `bridge` | Bridge VLAN table and bridge-port PVID (`/interface bridge vlan`, `/interface bridge port`) | [Bridge](bridge.md) |
| `wireguard` | WireGuard interfaces and peers | [WireGuard](wireguard.md) |
| `wireless` | Wi-Fi and wireless interfaces, security profiles and access lists | _no page yet_ |
| `poe` | Power over Ethernet monitoring | [PoE](poe.md) |

The tools of a module without a page are listed in the [API coverage checklist](../../api-coverage.md).
