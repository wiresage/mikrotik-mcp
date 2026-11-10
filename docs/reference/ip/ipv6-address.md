# IPv6 Address Management

Tools for managing IPv6 addresses on interfaces, under the RouterOS
`/ipv6 address` command tree. This is the IPv6 counterpart of the
[IP Address](address.md) (IPv4) scope.

> IPv6 lives in a separate command tree from IPv4 (`/ipv6 …` vs `/ip …`).
> These tools cover IPv6 *addressing*; IPv6 routing, firewall, DHCPv6/ND, and
> pools are separate areas.

## `add_ipv6_address`

Adds an IPv6 address to an interface. Runs `/ipv6 address add …`.

- Parameters:
  - `address` (required): IPv6 address with prefix length, e.g. `2001:db8::1/64`
    or `fe80::1/64`. With `from_pool`, supply the host part only (e.g. `::1/64`).
  - `interface` (required): interface name, e.g. `ether1`, `bridge`
  - `advertise` (optional): include this prefix in Router Advertisements
  - `eui_64` (optional): derive the host part of the address from the interface MAC
  - `from_pool` (optional): name of an IPv6 pool to take the prefix from
  - `no_dad` (optional): skip Duplicate Address Detection
  - `comment` (optional), `disabled` (optional)

- Examples:
  ```
  add_ipv6_address(address="2001:db8:1::1/64", interface="bridge")
  add_ipv6_address(address="2001:db8:1::1/64", interface="bridge", advertise=True)
  add_ipv6_address(address="::1/64", interface="bridge", from_pool="isp-pd")
  ```

## `list_ipv6_addresses`

Lists IPv6 addresses, with optional filtering. Runs `/ipv6 address print`.

- Parameters:
  - `interface_filter` (optional): filter by interface
  - `address_filter` (optional): partial match on the address, e.g. `"2001:db8"` or `"fe80"`
  - `disabled_only`, `dynamic_only`, `global_only`, `link_local_only` (optional)

- Examples:
  ```
  list_ipv6_addresses()
  list_ipv6_addresses(interface_filter="bridge")
  list_ipv6_addresses(global_only=True)        # routable addresses only
  list_ipv6_addresses(link_local_only=True)    # fe80::/10 only
  ```

## `get_ipv6_address`

Gets details for a single IPv6 address by RouterOS id or by address value.
Runs `/ipv6 address print detail where …`.

- Parameters:
  - `address_id` (required): internal id (e.g. `*1`) or the address value (e.g. `2001:db8::1/64`)

- Example:
  ```
  get_ipv6_address(address_id="2001:db8:1::1/64")
  ```

## `remove_ipv6_address`

Removes an IPv6 address by id or address value. Runs `/ipv6 address remove [find …]`.

- Parameters:
  - `address_id` (required): internal id (e.g. `*1`) or the address value

- Example:
  ```
  remove_ipv6_address(address_id="2001:db8:1::1/64")
  ```
