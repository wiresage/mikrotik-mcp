### Route Management

#### `add_route`
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
  add_route(dst_address="10.0.0.0/8", gateway="192.168.1.1")
  ```

#### `list_routes`
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
  list_routes(active_only=true)
  ```

#### `get_route`
Gets detailed information about a specific route.
- Parameters:
  - `route_id` (required): Route ID
- Example:
  ```
  get_route(route_id="*1")
  ```

#### `update_route`
Updates an existing route in MikroTik routing table.
- Parameters:
  - `route_id` (required): Route ID
  - All parameters from `add_route` (optional)
- Example:
  ```
  update_route(route_id="*1", comment="Updated route")
  ```

#### `remove_route`
Removes a route from MikroTik routing table.
- Parameters:
  - `route_id` (required): Route ID
- Example:
  ```
  remove_route(route_id="*1")
  ```

#### `enable_route`
Enables a route.
- Parameters:
  - `route_id` (required): Route ID
- Example:
  ```
  enable_route(route_id="*1")
  ```

#### `disable_route`
Disables a route.
- Parameters:
  - `route_id` (required): Route ID
- Example:
  ```
  disable_route(route_id="*1")
  ```

#### `get_routing_table`
Gets a specific routing table.
- Parameters:
  - `table_name` (optional): Table name (default: "main")
  - `protocol_filter` (optional): Filter by protocol
  - `active_only` (optional): Show only active routes
- Example:
  ```
  get_routing_table(table_name="main")
  ```

#### `check_route_path`
Checks the route path to a destination.
- Parameters:
  - `destination` (required): Destination address
  - `source` (optional): Source address
  - `routing_table` (optional): Routing table name from `/routing table` (RouterOS 6 called this the routing mark)
- Example:
  ```
  check_route_path(destination="8.8.8.8")
  ```

#### `get_route_cache`
Gets the route cache.
- Parameters: None
- Example:
  ```
  get_route_cache()
  ```

#### `flush_route_cache`
Flushes the route cache.
- Parameters: None
- Example:
  ```
  flush_route_cache()
  ```

#### `add_default_route`
Adds a default route (0.0.0.0/0).
- Parameters:
  - `gateway` (required): Gateway address
  - `distance` (optional): Administrative distance
  - `comment` (optional): Description
  - `check_gateway` (optional): Gateway check method
- Example:
  ```
  add_default_route(gateway="192.168.1.1")
  ```

#### `add_blackhole_route`
Adds a blackhole route.
- Parameters:
  - `dst_address` (required): Destination address
  - `distance` (optional): Administrative distance
  - `comment` (optional): Description
- Example:
  ```
  add_blackhole_route(dst_address="10.0.0.0/8")
  ```

#### `get_route_statistics`
Gets routing table statistics.
- Parameters: None
- Example:
  ```
  get_route_statistics()
  ```

