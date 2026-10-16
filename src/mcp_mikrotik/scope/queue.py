from typing import Literal, Optional
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ..connector import execute_mikrotik_command
from ._selectors import has_item_rows


# ───────────────────────────────────────────────
# Queue Types
# ───────────────────────────────────────────────

@mcp.tool(name="create_queue_type", annotations=annotate(WRITE, "Create Queue Type"))
async def mikrotik_create_queue_type(
    ctx: Context,
    name: str,
    kind: Literal["cake", "fq-codel", "sfq", "red", "pcq", "pfifo", "bfifo",
                   "pfifo-bpf", "mq-pfifo", "none"] = "cake",
    cake_flowmode: Optional[Literal["triple-isolate", "dual-srchost", "dual-dsthost",
                                     "host", "flow", "none"]] = None,
    cake_nat: Optional[bool] = None,
    cake_overhead: Optional[int] = None,
    cake_mpu: Optional[int] = None,
    cake_diffserv: Optional[Literal["besteffort", "diffserv3", "diffserv4", "diffserv8"]] = None,
    cake_ack_filter: Optional[Literal["filter", "aggressive", "none"]] = None,
    cake_rtt: Optional[str] = None,
    cake_wash: Optional[bool] = None,
    cake_overhead_scheme: Optional[str] = None,
    pcq_rate: Optional[str] = None,
    pcq_limit: Optional[int] = None,
    pcq_classifier: Optional[str] = None,
    pfifo_limit: Optional[int] = None,
    bfifo_limit: Optional[int] = None,
    sfq_perturb: Optional[int] = None,
    sfq_allot: Optional[int] = None,
    fq_codel_limit: Optional[int] = None,
    fq_codel_quantum: Optional[int] = None,
    fq_codel_target: Optional[str] = None,
    fq_codel_interval: Optional[str] = None,
    red_limit: Optional[int] = None,
    red_min_threshold: Optional[int] = None,
    red_max_threshold: Optional[int] = None,
    red_burst: Optional[int] = None,
    red_avg_packet: Optional[int] = None,
    device: Optional[str] = None,
) -> str:
    """Creates a queue type (qdisc). kind selects the discipline (cake, fq-codel, sfq, red, pcq, pfifo, bfifo); remaining params are per-discipline options.

    Notes:
        pcq_rate: bandwidth per flow e.g. "1M", "512k"
        pcq_classifier: comma-separated classifiers e.g. "src-address,dst-address"
        cake_rtt: round-trip time e.g. "50ms", "100ms"
        fq_codel_target / fq_codel_interval: time e.g. "5ms", "100ms"
    """
    await ctx.info(f"Creating queue type: name={name}, kind={kind}")

    cmd = f"/queue type add name={name} kind={kind}"

    # CAKE parameters
    if cake_flowmode is not None:
        cmd += f" cake-flowmode={cake_flowmode}"
    if cake_nat is not None:
        cmd += f' cake-nat={"yes" if cake_nat else "no"}'
    if cake_overhead is not None:
        cmd += f" cake-overhead={cake_overhead}"
    if cake_mpu is not None:
        cmd += f" cake-mpu={cake_mpu}"
    if cake_diffserv is not None:
        cmd += f" cake-diffserv={cake_diffserv}"
    if cake_ack_filter is not None:
        cmd += f" cake-ack-filter={cake_ack_filter}"
    if cake_rtt is not None:
        cmd += f" cake-rtt={cake_rtt}"
    if cake_wash is not None:
        cmd += f' cake-wash={"yes" if cake_wash else "no"}'
    if cake_overhead_scheme is not None:
        cmd += f" cake-overhead-scheme={cake_overhead_scheme}"

    # PCQ parameters
    if pcq_rate is not None:
        cmd += f" pcq-rate={pcq_rate}"
    if pcq_limit is not None:
        cmd += f" pcq-limit={pcq_limit}"
    if pcq_classifier is not None:
        cmd += f" pcq-classifier={pcq_classifier}"

    # PFIFO/BFIFO parameters
    if pfifo_limit is not None:
        cmd += f" pfifo-limit={pfifo_limit}"
    if bfifo_limit is not None:
        cmd += f" bfifo-limit={bfifo_limit}"

    # SFQ parameters
    if sfq_perturb is not None:
        cmd += f" sfq-perturb={sfq_perturb}"
    if sfq_allot is not None:
        cmd += f" sfq-allot={sfq_allot}"

    # FQ-CoDel parameters
    if fq_codel_limit is not None:
        cmd += f" fq-codel-limit={fq_codel_limit}"
    if fq_codel_quantum is not None:
        cmd += f" fq-codel-quantum={fq_codel_quantum}"
    if fq_codel_target is not None:
        cmd += f" fq-codel-target={fq_codel_target}"
    if fq_codel_interval is not None:
        cmd += f" fq-codel-interval={fq_codel_interval}"

    # RED parameters
    if red_limit is not None:
        cmd += f" red-limit={red_limit}"
    if red_min_threshold is not None:
        cmd += f" red-min-threshold={red_min_threshold}"
    if red_max_threshold is not None:
        cmd += f" red-max-threshold={red_max_threshold}"
    if red_burst is not None:
        cmd += f" red-burst={red_burst}"
    if red_avg_packet is not None:
        cmd += f" red-avg-packet={red_avg_packet}"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if result.strip():
        if "*" in result or result.strip().isdigit():
            type_id = result.strip()
            details_cmd = f"/queue type print detail where .id={type_id}"
            details = await execute_mikrotik_command(details_cmd, ctx, device=device)
            if details.strip():
                return f"Queue type created successfully:\n\n{details}"
            return f"Queue type created with ID: {type_id}"
        elif "failure:" in result.lower() or "error" in result.lower():
            return f"Failed to create queue type: {result}"

    # Verify by fetching by name
    details_cmd = f'/queue type print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    if details.strip():
        return f"Queue type created successfully:\n\n{details}"
    return "Queue type creation completed but unable to verify."


@mcp.tool(name="list_queue_types", annotations=annotate(READ, "List Queue Types"))
async def mikrotik_list_queue_types(
    ctx: Context,
    name_filter: Optional[str] = None,
    kind_filter: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Lists queue types on the MikroTik device."""
    await ctx.info("Listing queue types")

    cmd = "/queue type print"
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if kind_filter:
        filters.append(f"kind={kind_filter}")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not result or result.strip() == "":
        return "No queue types found matching the criteria."
    return f"QUEUE TYPES:\n\n{result}"


@mcp.tool(name="get_queue_type", annotations=annotate(READ, "Get Queue Type"))
async def mikrotik_get_queue_type(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific queue type."""
    await ctx.info(f"Getting queue type details: name={name}")

    cmd = f'/queue type print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not has_item_rows(result):
        return f"Queue type '{name}' not found."
    return f"QUEUE TYPE DETAILS:\n\n{result}"


@mcp.tool(name="update_queue_type", annotations=annotate(WRITE_IDEMPOTENT, "Update Queue Type"))
async def mikrotik_update_queue_type(
    ctx: Context,
    name: str,
    new_name: Optional[str] = None,
    cake_flowmode: Optional[str] = None,
    cake_nat: Optional[bool] = None,
    cake_overhead: Optional[int] = None,
    cake_mpu: Optional[int] = None,
    cake_diffserv: Optional[str] = None,
    cake_ack_filter: Optional[str] = None,
    cake_rtt: Optional[str] = None,
    cake_wash: Optional[bool] = None,
    cake_overhead_scheme: Optional[str] = None,
    pcq_rate: Optional[str] = None,
    pcq_limit: Optional[int] = None,
    pcq_classifier: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing queue type's discipline-specific settings."""
    await ctx.info(f"Updating queue type: name={name}")

    cmd = f'/queue type set [find name="{name}"]'

    updates = []
    if new_name is not None:
        updates.append(f"name={new_name}")
    if cake_flowmode is not None:
        updates.append(f"cake-flowmode={cake_flowmode}")
    if cake_nat is not None:
        updates.append(f'cake-nat={"yes" if cake_nat else "no"}')
    if cake_overhead is not None:
        updates.append(f"cake-overhead={cake_overhead}")
    if cake_mpu is not None:
        updates.append(f"cake-mpu={cake_mpu}")
    if cake_diffserv is not None:
        updates.append(f"cake-diffserv={cake_diffserv}")
    if cake_ack_filter is not None:
        updates.append(f"cake-ack-filter={cake_ack_filter}")
    if cake_rtt is not None:
        updates.append(f"cake-rtt={cake_rtt}")
    if cake_wash is not None:
        updates.append(f'cake-wash={"yes" if cake_wash else "no"}')
    if cake_overhead_scheme is not None:
        updates.append(f"cake-overhead-scheme={cake_overhead_scheme}")
    if pcq_rate is not None:
        updates.append(f"pcq-rate={pcq_rate}")
    if pcq_limit is not None:
        updates.append(f"pcq-limit={pcq_limit}")
    if pcq_classifier is not None:
        updates.append(f"pcq-classifier={pcq_classifier}")

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update queue type: {result}"

    lookup_name = new_name if new_name else name
    details_cmd = f'/queue type print detail where name="{lookup_name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    return f"Queue type updated successfully:\n\n{details}"


@mcp.tool(name="remove_queue_type", annotations=annotate(DESTRUCTIVE, "Remove Queue Type"))
async def mikrotik_remove_queue_type(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Removes a queue type from the MikroTik device."""
    await ctx.info(f"Removing queue type: name={name}")

    cmd = f'/queue type remove [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove queue type: {result}"
    return f"Queue type '{name}' removed successfully."


# ───────────────────────────────────────────────
# Queue Trees
# ───────────────────────────────────────────────

@mcp.tool(name="create_queue_tree", annotations=annotate(WRITE, "Create Queue Tree"))
async def mikrotik_create_queue_tree(
    ctx: Context,
    name: str,
    parent: str,
    queue: Optional[str] = None,
    packet_mark: Optional[str] = None,
    max_limit: Optional[str] = None,
    limit_at: Optional[str] = None,
    burst_limit: Optional[str] = None,
    burst_threshold: Optional[str] = None,
    burst_time: Optional[str] = None,
    bucket_size: Optional[str] = None,
    priority: Optional[int] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None,
) -> str:
    """Creates a hierarchical queue tree entry attached to a parent interface or queue.

    Notes:
        max_limit / limit_at / burst_limit / burst_threshold: bandwidth e.g. "10M", "512k", "1G"
        burst_time: duration e.g. "8s"
        parent: interface name e.g. "ether1" or parent queue name
        priority: 1 (highest) – 8 (lowest)
    """
    await ctx.info(f"Creating queue tree: name={name}, parent={parent}")

    cmd = f"/queue tree add name={name} parent={parent}"

    if queue is not None:
        cmd += f" queue={queue}"
    if packet_mark is not None:
        cmd += f" packet-mark={packet_mark}"
    if max_limit is not None:
        cmd += f" max-limit={max_limit}"
    if limit_at is not None:
        cmd += f" limit-at={limit_at}"
    if burst_limit is not None:
        cmd += f" burst-limit={burst_limit}"
    if burst_threshold is not None:
        cmd += f" burst-threshold={burst_threshold}"
    if burst_time is not None:
        cmd += f" burst-time={burst_time}"
    if bucket_size is not None:
        cmd += f" bucket-size={bucket_size}"
    if priority is not None:
        cmd += f" priority={priority}"
    if comment:
        cmd += f' comment="{comment}"'
    if disabled:
        cmd += " disabled=yes"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if result.strip():
        if "*" in result or result.strip().isdigit():
            tree_id = result.strip()
            details_cmd = f"/queue tree print detail where .id={tree_id}"
            details = await execute_mikrotik_command(details_cmd, ctx, device=device)
            if details.strip():
                return f"Queue tree created successfully:\n\n{details}"
            return f"Queue tree created with ID: {tree_id}"
        elif "failure:" in result.lower() or "error" in result.lower():
            return f"Failed to create queue tree: {result}"

    details_cmd = f'/queue tree print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    if details.strip():
        return f"Queue tree created successfully:\n\n{details}"
    return "Queue tree creation completed but unable to verify."


@mcp.tool(name="list_queue_trees", annotations=annotate(READ, "List Queue Trees"))
async def mikrotik_list_queue_trees(
    ctx: Context,
    name_filter: Optional[str] = None,
    parent_filter: Optional[str] = None,
    disabled_only: bool = False,
    invalid_only: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists queue trees on the MikroTik device."""
    await ctx.info("Listing queue trees")

    cmd = "/queue tree print"
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if parent_filter:
        filters.append(f'parent="{parent_filter}"')
    if disabled_only:
        filters.append("disabled=yes")
    if invalid_only:
        filters.append("invalid=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not result or result.strip() == "":
        return "No queue trees found matching the criteria."
    return f"QUEUE TREES:\n\n{result}"


@mcp.tool(name="get_queue_tree", annotations=annotate(READ, "Get Queue Tree"))
async def mikrotik_get_queue_tree(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific queue tree."""
    await ctx.info(f"Getting queue tree details: name={name}")

    cmd = f'/queue tree print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not has_item_rows(result):
        return f"Queue tree '{name}' not found."
    return f"QUEUE TREE DETAILS:\n\n{result}"


@mcp.tool(name="update_queue_tree", annotations=annotate(WRITE_IDEMPOTENT, "Update Queue Tree"))
async def mikrotik_update_queue_tree(
    ctx: Context,
    name: str,
    new_name: Optional[str] = None,
    parent: Optional[str] = None,
    queue: Optional[str] = None,
    packet_mark: Optional[str] = None,
    max_limit: Optional[str] = None,
    limit_at: Optional[str] = None,
    burst_limit: Optional[str] = None,
    burst_threshold: Optional[str] = None,
    burst_time: Optional[str] = None,
    bucket_size: Optional[str] = None,
    priority: Optional[int] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing queue tree entry (bandwidth limits, parent, priority, etc.).

    Notes:
        max_limit / limit_at / burst_limit / burst_threshold: bandwidth e.g. "10M", "512k"
        burst_time: duration e.g. "8s"
        priority: 1 (highest) – 8 (lowest)
    """
    await ctx.info(f"Updating queue tree: name={name}")

    cmd = f'/queue tree set [find name="{name}"]'

    updates = []
    if new_name is not None:
        updates.append(f"name={new_name}")
    if parent is not None:
        updates.append(f"parent={parent}")
    if queue is not None:
        updates.append(f"queue={queue}")
    if packet_mark is not None:
        updates.append(f"packet-mark={packet_mark}")
    if max_limit is not None:
        updates.append(f"max-limit={max_limit}")
    if limit_at is not None:
        updates.append(f"limit-at={limit_at}")
    if burst_limit is not None:
        updates.append(f"burst-limit={burst_limit}")
    if burst_threshold is not None:
        updates.append(f"burst-threshold={burst_threshold}")
    if burst_time is not None:
        updates.append(f"burst-time={burst_time}")
    if bucket_size is not None:
        updates.append(f"bucket-size={bucket_size}")
    if priority is not None:
        updates.append(f"priority={priority}")
    if comment is not None:
        updates.append(f'comment="{comment}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update queue tree: {result}"

    lookup_name = new_name if new_name else name
    details_cmd = f'/queue tree print detail where name="{lookup_name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    return f"Queue tree updated successfully:\n\n{details}"


@mcp.tool(name="remove_queue_tree", annotations=annotate(DESTRUCTIVE, "Remove Queue Tree"))
async def mikrotik_remove_queue_tree(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Removes a queue tree from the MikroTik device."""
    await ctx.info(f"Removing queue tree: name={name}")

    cmd = f'/queue tree remove [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove queue tree: {result}"
    return f"Queue tree '{name}' removed successfully."


@mcp.tool(name="enable_queue_tree", annotations=annotate(WRITE_IDEMPOTENT, "Enable Queue Tree"))
async def mikrotik_enable_queue_tree(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Enables a queue tree."""
    await ctx.info(f"Enabling queue tree: name={name}")

    cmd = f'/queue tree set [find name="{name}"] disabled=no'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to enable queue tree: {result}"

    details_cmd = f'/queue tree print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    return f"Queue tree enabled:\n\n{details}"


@mcp.tool(name="disable_queue_tree", annotations=annotate(WRITE_IDEMPOTENT, "Disable Queue Tree"))
async def mikrotik_disable_queue_tree(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Disables a queue tree."""
    await ctx.info(f"Disabling queue tree: name={name}")

    cmd = f'/queue tree set [find name="{name}"] disabled=yes'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to disable queue tree: {result}"

    details_cmd = f'/queue tree print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    return f"Queue tree disabled:\n\n{details}"


# ───────────────────────────────────────────────
# Simple Queues
# ───────────────────────────────────────────────

@mcp.tool(name="create_simple_queue", annotations=annotate(WRITE, "Create Simple Queue"))
async def mikrotik_create_simple_queue(
    ctx: Context,
    name: str,
    target: str,
    dst: Optional[str] = None,
    max_limit: Optional[str] = None,
    limit_at: Optional[str] = None,
    burst_limit: Optional[str] = None,
    burst_threshold: Optional[str] = None,
    burst_time: Optional[str] = None,
    bucket_size: Optional[str] = None,
    queue: Optional[str] = None,
    parent: Optional[str] = None,
    priority: Optional[str] = None,
    packet_marks: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None,
) -> str:
    """Creates a simple queue to rate-limit a target address or interface.

    Notes:
        target: IP/CIDR or interface e.g. "192.168.1.0/24" or "ether1"
        max_limit / limit_at / burst_limit / burst_threshold: upload/download bandwidth
            as "UL/DL" e.g. "10M/10M", or single value e.g. "10M"
        burst_time: duration e.g. "8s"
        priority: 1 (highest) – 8 (lowest)
    """
    await ctx.info(f"Creating simple queue: name={name}, target={target}")

    cmd = f"/queue simple add name={name} target={target}"

    if dst is not None:
        cmd += f" dst={dst}"
    if max_limit is not None:
        cmd += f" max-limit={max_limit}"
    if limit_at is not None:
        cmd += f" limit-at={limit_at}"
    if burst_limit is not None:
        cmd += f" burst-limit={burst_limit}"
    if burst_threshold is not None:
        cmd += f" burst-threshold={burst_threshold}"
    if burst_time is not None:
        cmd += f" burst-time={burst_time}"
    if bucket_size is not None:
        cmd += f" bucket-size={bucket_size}"
    if queue is not None:
        cmd += f" queue={queue}"
    if parent is not None:
        cmd += f" parent={parent}"
    if priority is not None:
        cmd += f" priority={priority}"
    if packet_marks is not None:
        cmd += f" packet-marks={packet_marks}"
    if comment:
        cmd += f' comment="{comment}"'
    if disabled:
        cmd += " disabled=yes"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if result.strip():
        if "*" in result or result.strip().isdigit():
            queue_id = result.strip()
            details_cmd = f"/queue simple print detail where .id={queue_id}"
            details = await execute_mikrotik_command(details_cmd, ctx, device=device)
            if details.strip():
                return f"Simple queue created successfully:\n\n{details}"
            return f"Simple queue created with ID: {queue_id}"
        elif "failure:" in result.lower() or "error" in result.lower():
            return f"Failed to create simple queue: {result}"

    details_cmd = f'/queue simple print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    if details.strip():
        return f"Simple queue created successfully:\n\n{details}"
    return "Simple queue creation completed but unable to verify."


@mcp.tool(name="list_simple_queues", annotations=annotate(READ, "List Simple Queues"))
async def mikrotik_list_simple_queues(
    ctx: Context,
    name_filter: Optional[str] = None,
    target_filter: Optional[str] = None,
    disabled_only: bool = False,
    invalid_only: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists simple queues on the MikroTik device."""
    await ctx.info("Listing simple queues")

    cmd = "/queue simple print"
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if target_filter:
        filters.append(f'target~"{target_filter}"')
    if disabled_only:
        filters.append("disabled=yes")
    if invalid_only:
        filters.append("invalid=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not result or result.strip() == "":
        return "No simple queues found matching the criteria."
    return f"SIMPLE QUEUES:\n\n{result}"


@mcp.tool(name="get_simple_queue", annotations=annotate(READ, "Get Simple Queue"))
async def mikrotik_get_simple_queue(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific simple queue."""
    await ctx.info(f"Getting simple queue details: name={name}")

    cmd = f'/queue simple print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not has_item_rows(result):
        return f"Simple queue '{name}' not found."
    return f"SIMPLE QUEUE DETAILS:\n\n{result}"


@mcp.tool(name="update_simple_queue", annotations=annotate(WRITE_IDEMPOTENT, "Update Simple Queue"))
async def mikrotik_update_simple_queue(
    ctx: Context,
    name: str,
    new_name: Optional[str] = None,
    target: Optional[str] = None,
    dst: Optional[str] = None,
    max_limit: Optional[str] = None,
    limit_at: Optional[str] = None,
    burst_limit: Optional[str] = None,
    burst_threshold: Optional[str] = None,
    burst_time: Optional[str] = None,
    bucket_size: Optional[str] = None,
    queue: Optional[str] = None,
    parent: Optional[str] = None,
    priority: Optional[str] = None,
    packet_marks: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing simple queue's rate limits, target, or scheduling settings.

    Notes:
        target: IP/CIDR or interface e.g. "192.168.1.0/24" or "ether1"
        max_limit / limit_at / burst_limit / burst_threshold: upload/download bandwidth
            as "UL/DL" e.g. "10M/10M", or single value e.g. "10M"
        burst_time: duration e.g. "8s"
        priority: 1 (highest) – 8 (lowest)
    """
    await ctx.info(f"Updating simple queue: name={name}")

    cmd = f'/queue simple set [find name="{name}"]'

    updates = []
    if new_name is not None:
        updates.append(f"name={new_name}")
    if target is not None:
        updates.append(f"target={target}")
    if dst is not None:
        updates.append(f"dst={dst}")
    if max_limit is not None:
        updates.append(f"max-limit={max_limit}")
    if limit_at is not None:
        updates.append(f"limit-at={limit_at}")
    if burst_limit is not None:
        updates.append(f"burst-limit={burst_limit}")
    if burst_threshold is not None:
        updates.append(f"burst-threshold={burst_threshold}")
    if burst_time is not None:
        updates.append(f"burst-time={burst_time}")
    if bucket_size is not None:
        updates.append(f"bucket-size={bucket_size}")
    if queue is not None:
        updates.append(f"queue={queue}")
    if parent is not None:
        updates.append(f"parent={parent}")
    if priority is not None:
        updates.append(f"priority={priority}")
    if packet_marks is not None:
        updates.append(f"packet-marks={packet_marks}")
    if comment is not None:
        updates.append(f'comment="{comment}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update simple queue: {result}"

    lookup_name = new_name if new_name else name
    details_cmd = f'/queue simple print detail where name="{lookup_name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    return f"Simple queue updated successfully:\n\n{details}"


@mcp.tool(name="remove_simple_queue", annotations=annotate(DESTRUCTIVE, "Remove Simple Queue"))
async def mikrotik_remove_simple_queue(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Removes a simple queue from the MikroTik device."""
    await ctx.info(f"Removing simple queue: name={name}")

    cmd = f'/queue simple remove [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove simple queue: {result}"
    return f"Simple queue '{name}' removed successfully."


@mcp.tool(name="enable_simple_queue", annotations=annotate(WRITE_IDEMPOTENT, "Enable Simple Queue"))
async def mikrotik_enable_simple_queue(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Enables a simple queue."""
    await ctx.info(f"Enabling simple queue: name={name}")

    cmd = f'/queue simple set [find name="{name}"] disabled=no'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to enable simple queue: {result}"

    details_cmd = f'/queue simple print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    return f"Simple queue enabled:\n\n{details}"


@mcp.tool(name="disable_simple_queue", annotations=annotate(WRITE_IDEMPOTENT, "Disable Simple Queue"))
async def mikrotik_disable_simple_queue(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Disables a simple queue."""
    await ctx.info(f"Disabling simple queue: name={name}")

    cmd = f'/queue simple set [find name="{name}"] disabled=yes'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to disable simple queue: {result}"

    details_cmd = f'/queue simple print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)
    return f"Simple queue disabled:\n\n{details}"
