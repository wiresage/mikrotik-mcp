# Firewall Address Lists

Tools for managing firewall address lists, under the RouterOS
`/ip firewall address-list` and `/ipv6 firewall address-list` command trees.

> Unlike the filter scopes, IPv4 and IPv6 address lists share one set of tools.
> The entry schema is identical across families — only the command tree differs —
> so each tool takes a required `family` of `"ipv4"` or `"ipv6"` instead of
> duplicating seven tools per family.

Three behaviours are worth knowing before using these:

- **IPv6 stores host entries with an explicit `/128`.** Adding `2001:db8::5`
  stores `2001:db8::5/128`, so a bare lookup would not match. These tools
  canonicalise the address for you — pass either form.
- **List names are matched exactly, including spaces.** A list named
  `"internal NS "` with a trailing space is a different list from
  `"internal NS"`. Nothing is trimmed.
- **A hostname entry creates dynamic children.** `address=example.com` adds one
  static entry plus one dynamic entry per resolved address. Use `static_only`
  to exclude them. An entry with a `timeout` is also dynamic and does not
  survive a reboot.

## `create_address_list_entry`

Adds an entry. Runs `/ip|/ipv6 firewall address-list add`.

- Parameters:
  - `family` (required): `"ipv4"` or `"ipv6"`
  - `list_name` (required): list to add to; created implicitly if new
  - `address` (required): address, prefix, or hostname
  - `comment`, `timeout` (e.g. `1h`), `disabled` (optional)

- Examples:
  ```
  create_address_list_entry(family="ipv4", list_name="trusted", address="203.0.113.0/24")
  create_address_list_entry(family="ipv6", list_name="trusted", address="2001:db8::5")
  create_address_list_entry(family="ipv4", list_name="temp", address="203.0.113.9", timeout="1h")
  ```

## `list_address_list_entries`

Lists entries. Runs `… print [where …]`.

- Parameters:
  - `family` (required)
  - `list_filter` (optional): exact list name, trailing spaces included
  - `address_filter` / `comment_filter` (optional): partial match
  - `disabled_only` / `dynamic_only` / `static_only` (optional)

- Examples:
  ```
  list_address_list_entries(family="ipv4")
  list_address_list_entries(family="ipv4", list_filter="trusted", static_only=True)
  list_address_list_entries(family="ipv6", address_filter="2001:db8")
  ```

## `get_address_list_entry`

Gets one entry by list name and address.

- Parameters: `family`, `list_name`, `address` (all required)

- Example:
  ```
  get_address_list_entry(family="ipv6", list_name="trusted", address="2001:db8::5")
  ```

## `update_address_list_entry`

Updates an entry located by its current list name and address.

- Parameters: `family`, `list_name`, `address` (required); `new_list_name`,
  `comment`, `timeout`, `disabled` (optional). Pass `""` to clear `comment`
  or `timeout`.

The change is confirmed on the device before success is reported: a refusal
that RouterOS phrases without the words "failure" or "error" — a read-only
account answers `not enough permissions (9)` — is reported as a failure rather
than as a successful update.

- Example:
  ```
  update_address_list_entry(family="ipv4", list_name="temp", address="203.0.113.9", new_list_name="trusted")
  ```

## `remove_address_list_entry`

Removes the matching entry. Removing a hostname entry also clears the dynamic
entries RouterOS derived from it.

- Example:
  ```
  remove_address_list_entry(family="ipv4", list_name="trusted", address="203.0.113.0/24")
  ```

## `enable_address_list_entry` / `disable_address_list_entry`

Toggles an entry without removing it.

- Example:
  ```
  disable_address_list_entry(family="ipv4", list_name="trusted", address="203.0.113.0/24")
  ```
