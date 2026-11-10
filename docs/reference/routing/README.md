### Route Management

#### `mikrotik_add_route`
Adds a route to MikroTik routing table.
- Parameters:
  - `dst_address` (required): Destination address
  - `gateway` (required): Gateway address
  - `distance` (optional): Administrative distance
  - `scope` (optional): Route scope
  - `target_scope` (optional): Target scope
  - `routing_table` (optional): Routing table name from `/routing table` (RouterOS 6 called this the routing mark)
  - `comment` (optional): Description
  - `disabled` (optional): Disable route
  - `vrf_interface` (optional): VRF interface
  - `pref_src` (optional): Preferred source
  - `check_gateway` (optional): Gateway check method
- Example:
  ```
  mikrotik_add_route(dst_address="10.0.0.0/8", gateway="192.168.1.1")
  ```

#### `mikrotik_list_routes`
Lists routes in MikroTik routing table.
- Parameters:
  - `dst_filter` (optional): Filter by destination
  - `gateway_filter` (optional): Filter by gateway
  - `routing_table_filter` (optional): Filter by routing table name
  - `distance_filter` (optional): Filter by distance
  - `active_only` (optional): Show only active routes
  - `disabled_only` (optional): Show only disabled routes
  - `dynamic_only` (optional): Show only dynamic routes
  - `static_only` (optional): Show only static routes
- Example:
  ```
  mikrotik_list_routes(active_only=true)
  ```

#### `mikrotik_get_route`
Gets detailed information about a specific route.
- Parameters:
  - `route_id` (required): Route ID
- Example:
  ```
  mikrotik_get_route(route_id="*1")
  ```

#### `mikrotik_update_route`
Updates an existing route in MikroTik routing table.
- Parameters:
  - `route_id` (required): Route ID
  - All parameters from `add_route` (optional)
- Example:
  ```
  mikrotik_update_route(route_id="*1", comment="Updated route")
  ```

#### `mikrotik_remove_route`
Removes a route from MikroTik routing table.
- Parameters:
  - `route_id` (required): Route ID
- Example:
  ```
  mikrotik_remove_route(route_id="*1")
  ```

#### `mikrotik_enable_route`
Enables a route.
- Parameters:
  - `route_id` (required): Route ID
- Example:
  ```
  mikrotik_enable_route(route_id="*1")
  ```

#### `mikrotik_disable_route`
Disables a route.
- Parameters:
  - `route_id` (required): Route ID
- Example:
  ```
  mikrotik_disable_route(route_id="*1")
  ```

#### `mikrotik_get_routing_table`
Gets a specific routing table.
- Parameters:
  - `table_name` (optional): Table name (default: "main")
  - `protocol_filter` (optional): Filter by protocol
  - `active_only` (optional): Show only active routes
- Example:
  ```
  mikrotik_get_routing_table(table_name="main")
  ```

#### `mikrotik_check_route_path`
Checks the route path to a destination.
- Parameters:
  - `destination` (required): Destination address
  - `source` (optional): Source address
  - `routing_table` (optional): Routing table name from `/routing table` (RouterOS 6 called this the routing mark)
- Example:
  ```
  mikrotik_check_route_path(destination="8.8.8.8")
  ```

#### `mikrotik_get_route_cache`
Gets the route cache.
- Parameters: None
- Example:
  ```
  mikrotik_get_route_cache()
  ```

#### `mikrotik_flush_route_cache`
Flushes the route cache.
- Parameters: None
- Example:
  ```
  mikrotik_flush_route_cache()
  ```

#### `mikrotik_add_default_route`
Adds a default route (0.0.0.0/0).
- Parameters:
  - `gateway` (required): Gateway address
  - `distance` (optional): Administrative distance
  - `comment` (optional): Description
  - `check_gateway` (optional): Gateway check method
- Example:
  ```
  mikrotik_add_default_route(gateway="192.168.1.1")
  ```

#### `mikrotik_add_blackhole_route`
Adds a blackhole route.
- Parameters:
  - `dst_address` (required): Destination address
  - `distance` (optional): Administrative distance
  - `comment` (optional): Description
- Example:
  ```
  mikrotik_add_blackhole_route(dst_address="10.0.0.0/8")
  ```

#### `mikrotik_get_route_statistics`
Gets routing table statistics.
- Parameters: None
- Example:
  ```
  mikrotik_get_route_statistics()
  ```

