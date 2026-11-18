# Queue Management

MikroTik provides three queue subsystems managed by this area: **Queue Types** (disciplines), **Queue Trees** (hierarchical / HTB), and **Simple Queues** (per-target rate limiting).

---

## Queue Types

Queue types define the queuing discipline (algorithm) used by queue trees and simple queues. Built-in types (`default`, `default-small`, etc.) cannot be modified; custom types can be created, updated, and removed.

### `create_queue_type`

Creates a new queue type (queuing discipline).

- **Annotation:** `WRITE`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Unique name for the queue type |
| `kind` | Literal | Discipline: `cake`, `fq-codel`, `sfq`, `red`, `pcq`, `pfifo`, `bfifo`, `pfifo-bpf`, `mq-pfifo`, `none` (default: `cake`) |
| `cake_flowmode` | Optional[Literal] | Flow isolation: `triple-isolate`, `dual-srchost`, `dual-dsthost`, `host`, `flow`, `none` |
| `cake_nat` | Optional[bool] | Enable NAT-aware flow classification |
| `cake_overhead` | Optional[int] | Per-packet overhead in bytes (e.g. 34 for PPPoE) |
| `cake_mpu` | Optional[int] | Minimum packet unit in bytes |
| `cake_diffserv` | Optional[Literal] | DSCP scheme: `besteffort`, `diffserv3`, `diffserv4`, `diffserv8` |
| `cake_ack_filter` | Optional[Literal] | ACK filter: `filter`, `aggressive`, `none` |
| `cake_rtt` | Optional[str] | RTT estimate (e.g. `"100ms"`) |
| `cake_wash` | Optional[bool] | Clear DSCP markings on egress |
| `cake_overhead_scheme` | Optional[str] | Preset overhead scheme (e.g. `"pppoe-ptm"`) |
| `pcq_rate` | Optional[str] | PCQ per-connection rate limit |
| `pcq_limit` | Optional[int] | PCQ queue size limit |
| `pcq_classifier` | Optional[str] | PCQ classifier (`src-address`, `dst-address`, etc.) |
| `pfifo_limit` | Optional[int] | PFIFO packet limit |
| `bfifo_limit` | Optional[int] | BFIFO byte limit |
| `sfq_perturb` | Optional[int] | SFQ hash perturbation interval (seconds) |
| `sfq_allot` | Optional[int] | SFQ allotment |
| `fq_codel_limit` | Optional[int] | FQ-CoDel queue limit |
| `fq_codel_quantum` | Optional[int] | FQ-CoDel quantum |
| `fq_codel_target` | Optional[str] | FQ-CoDel target delay (e.g. `"5ms"`) |
| `fq_codel_interval` | Optional[str] | FQ-CoDel interval (e.g. `"100ms"`) |
| `red_limit` | Optional[int] | RED queue limit |
| `red_min_threshold` | Optional[int] | RED minimum threshold |
| `red_max_threshold` | Optional[int] | RED maximum threshold |
| `red_burst` | Optional[int] | RED burst size |
| `red_avg_packet` | Optional[int] | RED average packet size |

**Example:**
```
create_queue_type(
    name="cake-isp",
    kind="cake",
    cake_flowmode="triple-isolate",
    cake_nat=True,
    cake_overhead=34,
    cake_diffserv="diffserv4"
)
```

---

### `list_queue_types`

Lists queue types, optionally filtered.

- **Annotation:** `READ`

| Parameter | Type | Description |
|---|---|---|
| `name_filter` | Optional[str] | Partial name match |
| `kind_filter` | Optional[str] | Filter by discipline |

---

### `get_queue_type`

Gets detailed information about a specific queue type by name.

- **Annotation:** `READ`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Queue type name |

---

### `update_queue_type`

Updates an existing custom queue type.

- **Annotation:** `WRITE_IDEMPOTENT`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Current name |
| `new_name` | Optional[str] | New name |
| `cake_flowmode`, `cake_nat`, `cake_overhead`, `cake_mpu`, `cake_diffserv`, `cake_ack_filter`, `cake_rtt`, `cake_wash`, `cake_overhead_scheme` | Optional | Same as `create_queue_type` |
| `pcq_rate`, `pcq_limit`, `pcq_classifier` | Optional | Same as `create_queue_type` |

`kind` and the `pfifo`, `bfifo`, `sfq`, `fq_codel` and `red` parameters cannot be
changed here. To change them, create a new queue type with `create_queue_type`.

---

### `remove_queue_type`

Removes a custom queue type. Built-in types cannot be removed.

- **Annotation:** `DESTRUCTIVE`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Queue type name to remove |

---

## Queue Trees

Queue trees implement hierarchical queuing (HTB). Each tree entry must have a `parent` (an interface or another queue tree entry). Packet marks from the mangle table control traffic classification.

### `create_queue_tree`

Creates a queue tree entry.

- **Annotation:** `WRITE`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Entry name |
| `parent` | str | Parent interface or queue (e.g. `"bridge"`, `"global"`, `"pppoe-out1"`) |
| `queue` | Optional[str] | Queue type name (e.g. `"cake-isp"`) |
| `packet_mark` | Optional[str] | Mangle packet mark to match |
| `max_limit` | Optional[str] | Maximum bandwidth (e.g. `"100M"`, `"1G"`) |
| `limit_at` | Optional[str] | Committed information rate (CIR) |
| `burst_limit` | Optional[str] | Burst bandwidth ceiling |
| `burst_threshold` | Optional[str] | Burst activation threshold |
| `burst_time` | Optional[str] | Burst duration |
| `bucket_size` | Optional[str] | Token bucket size (e.g. `"0.01"`) |
| `priority` | Optional[int] | Priority 1–8 (1 = highest) |
| `comment` | Optional[str] | Human-readable comment |
| `disabled` | bool | Disable immediately after creation (default: `False`) |

**Example:**
```
create_queue_tree(
    name="isp-download",
    parent="bridge",
    queue="cake-isp",
    max_limit="100M",
    priority=1
)
```

---

### `list_queue_trees`

- **Annotation:** `READ`

| Parameter | Type | Description |
|---|---|---|
| `name_filter` | Optional[str] | Partial name match |
| `parent_filter` | Optional[str] | Filter by parent |
| `disabled_only` | bool | Show only disabled entries |
| `invalid_only` | bool | Show only invalid entries |

---

### `get_queue_tree`

- **Annotation:** `READ`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Queue tree entry name |

---

### `update_queue_tree`

- **Annotation:** `WRITE_IDEMPOTENT`

Accepts all creation parameters as optional overrides (plus `new_name`, `disabled`).

---

### `remove_queue_tree`

- **Annotation:** `DESTRUCTIVE`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Entry name to remove |

---

### `enable_queue_tree` / `disable_queue_tree`

Enable or disable a queue tree entry without changing other settings.

- **Annotation:** `WRITE_IDEMPOTENT`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Entry name |

---

## Simple Queues

Simple queues are the easiest way to rate-limit traffic per source address, destination, or interface. Unlike queue trees, they don't require mangle rules for basic usage.

### `create_simple_queue`

- **Annotation:** `WRITE`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Queue name |
| `target` | str | Source address or interface (e.g. `"192.168.1.0/24"`, `"ether1"`) |
| `dst` | Optional[str] | Destination address (e.g. `"0.0.0.0/0"`) |
| `max_limit` | Optional[str] | Max upload/download (e.g. `"10M/20M"`) |
| `limit_at` | Optional[str] | Guaranteed upload/download rate |
| `burst_limit` | Optional[str] | Burst upload/download ceiling |
| `burst_threshold` | Optional[str] | Burst activation threshold |
| `burst_time` | Optional[str] | Burst duration |
| `bucket_size` | Optional[str] | Token bucket (e.g. `"0.1/0.1"`) |
| `queue` | Optional[str] | Queue type for upload/download (e.g. `"default-small/default-small"`) |
| `parent` | Optional[str] | Parent queue name |
| `priority` | Optional[str] | Priority upload/download (e.g. `"8/8"`) |
| `packet_marks` | Optional[str] | Packet marks to match |
| `comment` | Optional[str] | Human-readable comment |
| `disabled` | bool | Disable immediately after creation (default: `False`) |

**Example:**
```
create_simple_queue(
    name="guest-limit",
    target="192.168.10.0/24",
    max_limit="5M/5M",
    comment="Guest network speed cap"
)
```

---

### `list_simple_queues`

- **Annotation:** `READ`

| Parameter | Type | Description |
|---|---|---|
| `name_filter` | Optional[str] | Partial name match |
| `target_filter` | Optional[str] | Filter by target address |
| `disabled_only` | bool | Show only disabled queues |
| `invalid_only` | bool | Show only invalid queues |

---

### `get_simple_queue`

- **Annotation:** `READ`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Queue name |

---

### `update_simple_queue`

- **Annotation:** `WRITE_IDEMPOTENT`

Accepts all creation parameters as optional overrides (plus `new_name`, `disabled`).

---

### `remove_simple_queue`

- **Annotation:** `DESTRUCTIVE`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Queue name to remove |

---

### `enable_simple_queue` / `disable_simple_queue`

- **Annotation:** `WRITE_IDEMPOTENT`

| Parameter | Type | Description |
|---|---|---|
| `name` | str | Queue name |

---

## Typical Workflow — ISP Bandwidth Management

```
# 1. Create a CAKE queue type tuned for PPPoE links
create_queue_type(
    name="cake-pppoe",
    kind="cake",
    cake_flowmode="triple-isolate",
    cake_nat=True,
    cake_overhead=34
)

# 2. Create a root queue tree on the WAN interface
create_queue_tree(name="wan-root", parent="pppoe-out1", queue="cake-pppoe", max_limit="100M")

# 3. Create child queues per traffic class
create_queue_tree(name="bulk",     parent="wan-root", packet_mark="bulk-traffic",   priority=8, max_limit="100M")
create_queue_tree(name="realtime", parent="wan-root", packet_mark="rt-traffic",     priority=1, max_limit="100M")

# 4. Or use simple queues for per-client limits
create_simple_queue(name="client-001", target="192.168.1.10", max_limit="25M/25M")
```
