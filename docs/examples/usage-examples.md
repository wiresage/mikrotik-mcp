## Usage Examples with mcp-cli

These commands use [mcp-cli](https://github.com/chrishayuk/mcp-cli) with a server named
`mikrotik` in its configuration file. Tool names are the names the server registers,
such as `list_vlan_interfaces`.

### VLAN Interface Operations
```bash
# Create a VLAN interface
uvx mcp-cli cmd --server mikrotik --tool create_vlan_interface --tool-args '{"name": "vlan100", "vlan_id": 100, "interface": "ether1", "comment": "Production VLAN"}'

# List all VLANs
uvx mcp-cli cmd --server mikrotik --tool list_vlan_interfaces --tool-args '{}'

# Get specific VLAN details
uvx mcp-cli cmd --server mikrotik --tool get_vlan_interface --tool-args '{"name": "vlan100"}'

# Update VLAN interface
uvx mcp-cli cmd --server mikrotik --tool update_vlan_interface --tool-args '{"name": "vlan100", "comment": "Updated Production VLAN"}'

# Remove VLAN interface
uvx mcp-cli cmd --server mikrotik --tool remove_vlan_interface --tool-args '{"name": "vlan100"}'
```

### IP Address Management
```bash
# Add IP address to interface
uvx mcp-cli cmd --server mikrotik --tool add_ip_address --tool-args '{"address": "192.168.100.1/24", "interface": "vlan100", "comment": "Gateway address"}'

# List IP addresses
uvx mcp-cli cmd --server mikrotik --tool list_ip_addresses --tool-args '{"interface_filter": "vlan100"}'

# Get specific IP address
uvx mcp-cli cmd --server mikrotik --tool get_ip_address --tool-args '{"address_id": "*1"}'

# Remove IP address
uvx mcp-cli cmd --server mikrotik --tool remove_ip_address --tool-args '{"address_id": "*1"}'
```

### DHCP Server Configuration
```bash
# Create DHCP pool
uvx mcp-cli cmd --server mikrotik --tool create_dhcp_pool --tool-args '{"name": "pool-vlan100", "ranges": "192.168.100.10-192.168.100.200"}'

# Create DHCP network
uvx mcp-cli cmd --server mikrotik --tool create_dhcp_network --tool-args '{"network": "192.168.100.0/24", "gateway": "192.168.100.1", "dns_servers": ["8.8.8.8", "8.8.4.4"]}'

# Create DHCP server
uvx mcp-cli cmd --server mikrotik --tool create_dhcp_server --tool-args '{"name": "dhcp-vlan100", "interface": "vlan100", "address_pool": "pool-vlan100"}'

# List DHCP servers
uvx mcp-cli cmd --server mikrotik --tool list_dhcp_servers --tool-args '{}'

# Get DHCP server details
uvx mcp-cli cmd --server mikrotik --tool get_dhcp_server --tool-args '{"name": "dhcp-vlan100"}'

# Remove DHCP server
uvx mcp-cli cmd --server mikrotik --tool remove_dhcp_server --tool-args '{"name": "dhcp-vlan100"}'
```

### NAT Rule Management
```bash
# Create masquerade rule
uvx mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "srcnat", "action": "masquerade", "out_interface": "ether1", "comment": "Internet access"}'

# Create port forwarding rule
uvx mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "dstnat", "action": "dst-nat", "dst_port": "80", "protocol": "tcp", "to_addresses": "192.168.100.10", "to_ports": "80", "comment": "Web server"}'

# List NAT rules
uvx mcp-cli cmd --server mikrotik --tool list_nat_rules --tool-args '{"chain_filter": "srcnat"}'

# Get NAT rule details
uvx mcp-cli cmd --server mikrotik --tool get_nat_rule --tool-args '{"rule_id": "*1"}'

# Move NAT rule
uvx mcp-cli cmd --server mikrotik --tool move_nat_rule --tool-args '{"rule_id": "*1", "destination": 0}'

# Enable/Disable NAT rule
uvx mcp-cli cmd --server mikrotik --tool disable_nat_rule --tool-args '{"rule_id": "*1"}'
uvx mcp-cli cmd --server mikrotik --tool enable_nat_rule --tool-args '{"rule_id": "*1"}'

# Remove NAT rule
uvx mcp-cli cmd --server mikrotik --tool remove_nat_rule --tool-args '{"rule_id": "*1"}'
```

### IP Pool Management
```bash
# Create IP pool
uvx mcp-cli cmd --server mikrotik --tool create_ip_pool --tool-args '{"name": "main-pool", "ranges": "192.168.1.100-192.168.1.200"}'

# List IP pools
uvx mcp-cli cmd --server mikrotik --tool list_ip_pools --tool-args '{"include_used": true}'

# Get IP pool details
uvx mcp-cli cmd --server mikrotik --tool get_ip_pool --tool-args '{"name": "main-pool"}'

# List used addresses in pool
uvx mcp-cli cmd --server mikrotik --tool list_ip_pool_used --tool-args '{"pool_name": "main-pool"}'

# Expand IP pool
uvx mcp-cli cmd --server mikrotik --tool expand_ip_pool --tool-args '{"name": "main-pool", "additional_ranges": "192.168.1.201-192.168.1.250"}'

# Remove IP pool
uvx mcp-cli cmd --server mikrotik --tool remove_ip_pool --tool-args '{"name": "main-pool"}'
```

### Backup and Export
```bash
# Create system backup
uvx mcp-cli cmd --server mikrotik --tool create_backup --tool-args '{"name": "full_backup", "include_password": true}'

# Create configuration export
uvx mcp-cli cmd --server mikrotik --tool create_export --tool-args '{"name": "config_export", "file_format": "rsc", "export_type": "full"}'

# Export specific section
uvx mcp-cli cmd --server mikrotik --tool export_section --tool-args '{"section": "/ip/firewall"}'

# List backups
uvx mcp-cli cmd --server mikrotik --tool list_backups --tool-args '{"include_exports": true}'

# Download file
uvx mcp-cli cmd --server mikrotik --tool download_file --tool-args '{"filename": "full_backup.backup"}'

# Upload file
uvx mcp-cli cmd --server mikrotik --tool upload_file --tool-args '{"filename": "config.rsc", "content_base64": "base64_encoded_content"}'

# Restore backup
uvx mcp-cli cmd --server mikrotik --tool restore_backup --tool-args '{"filename": "full_backup.backup"}'

# Import configuration
uvx mcp-cli cmd --server mikrotik --tool import_configuration --tool-args '{"filename": "config.rsc"}'

# Remove file
uvx mcp-cli cmd --server mikrotik --tool remove_file --tool-args '{"filename": "old_backup.backup"}'
```

### Log Management
```bash
# Get logs
uvx mcp-cli cmd --server mikrotik --tool get_logs --tool-args '{"topics": "firewall", "limit": 100}'

# Get logs by severity
uvx mcp-cli cmd --server mikrotik --tool get_logs_by_severity --tool-args '{"severity": "error", "limit": 50}'

# Search logs
uvx mcp-cli cmd --server mikrotik --tool search_logs --tool-args '{"search_term": "login failed", "case_sensitive": false}'

# Get security logs
uvx mcp-cli cmd --server mikrotik --tool get_security_logs --tool-args '{"limit": 100}'

# Get log statistics
uvx mcp-cli cmd --server mikrotik --tool get_log_statistics --tool-args '{}'

# Export logs
uvx mcp-cli cmd --server mikrotik --tool export_logs --tool-args '{"filename": "firewall_logs", "topics": "firewall"}'

# Monitor logs
uvx mcp-cli cmd --server mikrotik --tool monitor_logs --tool-args '{"topics": "firewall", "duration": 30}'

# Clear logs
uvx mcp-cli cmd --server mikrotik --tool clear_logs --tool-args '{}'
```

### Firewall Filter Rules
```bash
# Create basic firewall rules
uvx mcp-cli cmd --server mikrotik --tool create_filter_rule --tool-args '{"chain": "input", "action": "accept", "connection_state": "established,related", "comment": "Accept established"}'
uvx mcp-cli cmd --server mikrotik --tool create_filter_rule --tool-args '{"chain": "input", "action": "drop", "connection_state": "invalid", "comment": "Drop invalid"}'
uvx mcp-cli cmd --server mikrotik --tool create_filter_rule --tool-args '{"chain": "input", "action": "accept", "protocol": "icmp", "comment": "Accept ICMP"}'

# List firewall rules
uvx mcp-cli cmd --server mikrotik --tool list_filter_rules --tool-args '{"chain_filter": "input"}'

# Get firewall rule details
uvx mcp-cli cmd --server mikrotik --tool get_filter_rule --tool-args '{"rule_id": "*1"}'

# Move firewall rule
uvx mcp-cli cmd --server mikrotik --tool move_filter_rule --tool-args '{"rule_id": "*1", "destination": 0}'

# Enable/Disable firewall rule
uvx mcp-cli cmd --server mikrotik --tool disable_filter_rule --tool-args '{"rule_id": "*1"}'
uvx mcp-cli cmd --server mikrotik --tool enable_filter_rule --tool-args '{"rule_id": "*1"}'

# Create basic firewall setup
uvx mcp-cli cmd --server mikrotik --tool create_basic_firewall_setup --tool-args '{}'

# Remove firewall rule
uvx mcp-cli cmd --server mikrotik --tool remove_filter_rule --tool-args '{"rule_id": "*1"}'
```

### Route Management
```bash
# Add route
uvx mcp-cli cmd --server mikrotik --tool add_route --tool-args '{"dst_address": "10.0.0.0/8", "gateway": "192.168.1.1", "comment": "Corporate network"}'

# Add default route
uvx mcp-cli cmd --server mikrotik --tool add_default_route --tool-args '{"gateway": "192.168.1.1", "distance": 1}'

# Add blackhole route
uvx mcp-cli cmd --server mikrotik --tool add_blackhole_route --tool-args '{"dst_address": "192.168.99.0/24", "comment": "Block subnet"}'

# List routes
uvx mcp-cli cmd --server mikrotik --tool list_routes --tool-args '{"active_only": true}'

# Get route details
uvx mcp-cli cmd --server mikrotik --tool get_route --tool-args '{"route_id": "*1"}'

# Check route path
uvx mcp-cli cmd --server mikrotik --tool check_route_path --tool-args '{"destination": "8.8.8.8"}'

# Get routing table
uvx mcp-cli cmd --server mikrotik --tool get_routing_table --tool-args '{"table_name": "main"}'

# Get route statistics
uvx mcp-cli cmd --server mikrotik --tool get_route_statistics --tool-args '{}'

# Enable/Disable route
uvx mcp-cli cmd --server mikrotik --tool disable_route --tool-args '{"route_id": "*1"}'
uvx mcp-cli cmd --server mikrotik --tool enable_route --tool-args '{"route_id": "*1"}'

# Remove route
uvx mcp-cli cmd --server mikrotik --tool remove_route --tool-args '{"route_id": "*1"}'
```

### DNS Configuration
```bash
# Set DNS servers
uvx mcp-cli cmd --server mikrotik --tool set_dns_servers --tool-args '{"servers": ["8.8.8.8", "8.8.4.4"], "allow_remote_requests": true}'

# Get DNS settings
uvx mcp-cli cmd --server mikrotik --tool get_dns_settings --tool-args '{}'

# Add static DNS entry
uvx mcp-cli cmd --server mikrotik --tool add_dns_static --tool-args '{"name": "router.local", "address": "192.168.1.1", "comment": "Local router"}'

# Add CNAME record
uvx mcp-cli cmd --server mikrotik --tool add_dns_static --tool-args '{"name": "www.example.com", "cname": "example.com"}'

# List static DNS entries
uvx mcp-cli cmd --server mikrotik --tool list_dns_static --tool-args '{"name_filter": "local"}'

# Update DNS entry
uvx mcp-cli cmd --server mikrotik --tool update_dns_static --tool-args '{"entry_id": "*1", "address": "192.168.1.2"}'

# Add DNS regexp
uvx mcp-cli cmd --server mikrotik --tool add_dns_regexp --tool-args '{"regexp": ".*\\.ads\\..*", "address": "0.0.0.0", "comment": "Block ads"}'

# Test DNS query
uvx mcp-cli cmd --server mikrotik --tool test_dns_query --tool-args '{"name": "google.com"}'

# Get DNS cache
uvx mcp-cli cmd --server mikrotik --tool get_dns_cache --tool-args '{}'

# Flush DNS cache
uvx mcp-cli cmd --server mikrotik --tool flush_dns_cache --tool-args '{}'

# Export DNS config
uvx mcp-cli cmd --server mikrotik --tool export_dns_config --tool-args '{"filename": "dns_config"}'

# Remove DNS entry
uvx mcp-cli cmd --server mikrotik --tool remove_dns_static --tool-args '{"entry_id": "*1"}'
```

### User Management
```bash
# Add user
uvx mcp-cli cmd --server mikrotik --tool add_user --tool-args '{"name": "newuser", "password": "SecurePass123", "group": "write", "comment": "New operator"}'

# List users
uvx mcp-cli cmd --server mikrotik --tool list_users --tool-args '{"group_filter": "write"}'

# Get user details
uvx mcp-cli cmd --server mikrotik --tool get_user --tool-args '{"name": "newuser"}'

# Update user
uvx mcp-cli cmd --server mikrotik --tool update_user --tool-args '{"name": "newuser", "password": "NewSecurePass456"}'

# Enable/Disable user
uvx mcp-cli cmd --server mikrotik --tool disable_user --tool-args '{"name": "newuser"}'
uvx mcp-cli cmd --server mikrotik --tool enable_user --tool-args '{"name": "newuser"}'

# Add user group
uvx mcp-cli cmd --server mikrotik --tool add_user_group --tool-args '{"name": "operators", "policy": ["read", "write", "test"], "comment": "Operator group"}'

# List user groups
uvx mcp-cli cmd --server mikrotik --tool list_user_groups --tool-args '{}'

# Get active users
uvx mcp-cli cmd --server mikrotik --tool get_active_users --tool-args '{}'

# Export user config
uvx mcp-cli cmd --server mikrotik --tool export_user_config --tool-args '{"filename": "user_config"}'

# Remove user
uvx mcp-cli cmd --server mikrotik --tool remove_user --tool-args '{"name": "newuser"}'
```

### Complete Workflows

#### Setting Up a New Network Segment
```bash
# Create VLAN
uvx mcp-cli cmd --server mikrotik --tool create_vlan_interface --tool-args '{"name": "vlan200", "vlan_id": 200, "interface": "ether1", "comment": "Guest Network"}'

# Add IP address
uvx mcp-cli cmd --server mikrotik --tool add_ip_address --tool-args '{"address": "192.168.200.1/24", "interface": "vlan200"}'

# Create DHCP pool
uvx mcp-cli cmd --server mikrotik --tool create_dhcp_pool --tool-args '{"name": "pool-200", "ranges": "192.168.200.10-192.168.200.100"}'

# Create DHCP network
uvx mcp-cli cmd --server mikrotik --tool create_dhcp_network --tool-args '{"network": "192.168.200.0/24", "gateway": "192.168.200.1", "dns_servers": ["8.8.8.8", "8.8.4.4"]}'

# Create DHCP server
uvx mcp-cli cmd --server mikrotik --tool create_dhcp_server --tool-args '{"name": "dhcp-200", "interface": "vlan200", "address_pool": "pool-200"}'

# Create NAT rule
uvx mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "srcnat", "action": "masquerade", "out_interface": "ether1", "comment": "Internet access for VLAN 200"}'
```

#### Port Forwarding Setup
```bash
# Forward HTTP traffic
uvx mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "dstnat", "action": "dst-nat", "dst_address": "203.0.113.1", "dst_port": "80", "protocol": "tcp", "to_addresses": "192.168.100.10", "to_ports": "80", "comment": "Web server"}'

# Forward HTTPS traffic
uvx mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "dstnat", "action": "dst-nat", "dst_address": "203.0.113.1", "dst_port": "443", "protocol": "tcp", "to_addresses": "192.168.100.10", "to_ports": "443", "comment": "HTTPS server"}'

# Forward custom SSH port
uvx mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "dstnat", "action": "dst-nat", "dst_address": "203.0.113.1", "dst_port": "2222", "protocol": "tcp", "to_addresses": "192.168.100.10", "to_ports": "22", "comment": "SSH server"}'
```

#### Backup and Restore Process
```bash
# Create backup user
uvx mcp-cli cmd --server mikrotik --tool add_user --tool-args '{"name": "backup_user", "password": "BackupPass123", "group": "read", "comment": "Backup account"}'

# Create full backup
uvx mcp-cli cmd --server mikrotik --tool create_backup --tool-args '{"name": "daily_backup", "include_password": true}'

# Export configuration
uvx mcp-cli cmd --server mikrotik --tool create_export --tool-args '{"name": "config_export", "file_format": "rsc", "export_type": "full"}'

# Export firewall rules
uvx mcp-cli cmd --server mikrotik --tool export_section --tool-args '{"section": "/ip/firewall/filter"}'

# Export NAT rules
uvx mcp-cli cmd --server mikrotik --tool export_section --tool-args '{"section": "/ip/firewall/nat"}'
```

### Create Wireless Interface
```bash
# Create basic AP interface
uvx mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wlan1", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "MyNetwork", "comment": "Main WiFi Network"}'

# Create station interface
uvx mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wlan-sta", "radio_name": "wlan2", "mode": "station", "ssid": "UpstreamWiFi"}'

# Create with specific frequency and band
uvx mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wlan-5g", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "MyNetwork-5G", "frequency": "5180", "band": "5ghz-a/n/ac", "channel_width": "80mhz"}'
```

### List and Manage Wireless Interfaces
```bash
# List all wireless interfaces
uvx mcp-cli cmd --server mikrotik --tool list_wireless_interfaces --tool-args '{}'

# List only running interfaces
uvx mcp-cli cmd --server mikrotik --tool list_wireless_interfaces --tool-args '{"running_only": true}'

# Get specific interface details
uvx mcp-cli cmd --server mikrotik --tool get_wireless_interface --tool-args '{"name": "wlan1"}'

# Update wireless interface
uvx mcp-cli cmd --server mikrotik --tool update_wireless_interface --tool-args '{"name": "wlan1", "ssid": "UpdatedNetworkName", "comment": "Updated main network"}'

# Enable/Disable wireless interface
uvx mcp-cli cmd --server mikrotik --tool disable_wireless_interface --tool-args '{"name": "wlan1"}'
uvx mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "wlan1"}'

# Remove wireless interface
uvx mcp-cli cmd --server mikrotik --tool remove_wireless_interface --tool-args '{"name": "wlan-guest"}'
```

### Wireless Security and Access Lists

RouterOS 7 configures WiFi security on the interface, so use `set_wireless_passphrase`:

```bash
uvx mcp-cli cmd --server mikrotik --tool set_wireless_passphrase --tool-args '{"name": "wlan1", "passphrase": "change-me-please", "authentication_types": "wpa2-psk"}'
```

The `*_wireless_security_profile*` and `*_wireless_access_list*` tools are legacy
placeholders. They return an explanatory message and change nothing on the device.

### Wireless Network Operations

#### Network Scanning and Monitoring
```bash
# Scan for available networks
uvx mcp-cli cmd --server mikrotik --tool scan_wireless_networks --tool-args '{"interface": "wlan1", "duration": 10}'

# Quick scan (5 seconds)
uvx mcp-cli cmd --server mikrotik --tool scan_wireless_networks --tool-args '{"interface": "wlan2"}'

# Get connected clients (all interfaces)
uvx mcp-cli cmd --server mikrotik --tool get_wireless_registration_table --tool-args '{}'

# Get clients for specific interface
uvx mcp-cli cmd --server mikrotik --tool get_wireless_registration_table --tool-args '{"interface": "wlan1"}'
```

### Complete WiFi Network Setup Examples

#### Basic Home Network Setup
```bash
# 1. Create wireless interface
uvx mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "home-wifi", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "HomeNetwork", "band": "2ghz-b/g/n", "comment": "Main home network"}'

# 2. Set the WiFi passphrase
uvx mcp-cli cmd --server mikrotik --tool set_wireless_passphrase --tool-args '{"name": "home-wifi", "passphrase": "change-me-please", "authentication_types": "wpa2-psk"}'

# 3. Enable the interface
uvx mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "home-wifi"}'
```

#### Guest Network Setup
```bash
# 1. Create guest wireless interface
uvx mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "guest-wifi", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "GuestNetwork", "comment": "Guest access network"}'

# 2. Enable guest network
uvx mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "guest-wifi"}'
```

#### Dual-Band Setup (2.4GHz + 5GHz)
```bash
# 1. Create 2.4GHz interface
uvx mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wifi-2g", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "MyNetwork", "band": "2ghz-b/g/n", "channel_width": "20mhz", "comment": "2.4GHz network"}'

# 2. Create 5GHz interface  
uvx mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wifi-5g", "radio_name": "wlan2", "mode": "ap-bridge", "ssid": "MyNetwork-5G", "band": "5ghz-a/n/ac", "channel_width": "80mhz", "comment": "5GHz network"}'

# 3. Set the passphrase on both interfaces
uvx mcp-cli cmd --server mikrotik --tool set_wireless_passphrase --tool-args '{"name": "wifi-2g", "passphrase": "change-me-please", "authentication_types": "wpa2-psk"}'
uvx mcp-cli cmd --server mikrotik --tool set_wireless_passphrase --tool-args '{"name": "wifi-5g", "passphrase": "change-me-please", "authentication_types": "wpa2-psk"}'

# 4. Enable both interfaces
uvx mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "wifi-2g"}'
uvx mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "wifi-5g"}'
```

#### Point-to-Point Wireless Link
```bash
# On first device (Station)
uvx mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "p2p-station", "radio_name": "wlan1", "mode": "station", "ssid": "P2P-Link", "frequency": "5180", "band": "5ghz-a/n"}'

# On second device (AP)  
uvx mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "p2p-ap", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "P2P-Link", "frequency": "5180", "band": "5ghz-a/n"}'

# Set the passphrase on both ends
uvx mcp-cli cmd --server mikrotik --tool set_wireless_passphrase --tool-args '{"name": "p2p-station", "passphrase": "change-me-please", "authentication_types": "wpa2-psk"}'
uvx mcp-cli cmd --server mikrotik --tool set_wireless_passphrase --tool-args '{"name": "p2p-ap", "passphrase": "change-me-please", "authentication_types": "wpa2-psk"}'
```

### Monitoring and Troubleshooting

#### Network Analysis
```bash
# Scan for interference and available channels
uvx mcp-cli cmd --server mikrotik --tool scan_wireless_networks --tool-args '{"interface": "wlan1", "duration": 30}'

# Monitor connected clients
uvx mcp-cli cmd --server mikrotik --tool get_wireless_registration_table --tool-args '{"interface": "wlan1"}'

# Check interface status
uvx mcp-cli cmd --server mikrotik --tool get_wireless_interface --tool-args '{"name": "wlan1"}'

# List all wireless configurations
uvx mcp-cli cmd --server mikrotik --tool list_wireless_interfaces --tool-args '{}'
```

#### Maintenance Operations
```bash
# Disable interface for maintenance
uvx mcp-cli cmd --server mikrotik --tool disable_wireless_interface --tool-args '{"name": "wlan1"}'

# Update configuration
uvx mcp-cli cmd --server mikrotik --tool update_wireless_interface --tool-args '{"name": "wlan1", "comment": "Updated for better performance"}'

# Re-enable interface
uvx mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "wlan1"}'
```
