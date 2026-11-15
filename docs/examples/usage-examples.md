## Usage Examples with mcp-cli

### VLAN Interface Operations
```bash
# Create a VLAN interface
uv run mcp-cli cmd --server mikrotik --tool create_vlan_interface --tool-args '{"name": "vlan100", "vlan_id": 100, "interface": "ether1", "comment": "Production VLAN"}'

# List all VLANs
uv run mcp-cli cmd --server mikrotik --tool list_vlan_interfaces --tool-args '{}'

# Get specific VLAN details
uv run mcp-cli cmd --server mikrotik --tool get_vlan_interface --tool-args '{"name": "vlan100"}'

# Update VLAN interface
uv run mcp-cli cmd --server mikrotik --tool update_vlan_interface --tool-args '{"name": "vlan100", "comment": "Updated Production VLAN"}'

# Remove VLAN interface
uv run mcp-cli cmd --server mikrotik --tool remove_vlan_interface --tool-args '{"name": "vlan100"}'
```

### IP Address Management
```bash
# Add IP address to interface
uv run mcp-cli cmd --server mikrotik --tool add_ip_address --tool-args '{"address": "192.168.100.1/24", "interface": "vlan100", "comment": "Gateway address"}'

# List IP addresses
uv run mcp-cli cmd --server mikrotik --tool list_ip_addresses --tool-args '{"interface_filter": "vlan100"}'

# Get specific IP address
uv run mcp-cli cmd --server mikrotik --tool get_ip_address --tool-args '{"address_id": "*1"}'

# Remove IP address
uv run mcp-cli cmd --server mikrotik --tool remove_ip_address --tool-args '{"address_id": "*1"}'
```

### DHCP Server Configuration
```bash
# Create DHCP pool
uv run mcp-cli cmd --server mikrotik --tool create_dhcp_pool --tool-args '{"name": "pool-vlan100", "ranges": "192.168.100.10-192.168.100.200"}'

# Create DHCP network
uv run mcp-cli cmd --server mikrotik --tool create_dhcp_network --tool-args '{"network": "192.168.100.0/24", "gateway": "192.168.100.1", "dns_servers": ["8.8.8.8", "8.8.4.4"]}'

# Create DHCP server
uv run mcp-cli cmd --server mikrotik --tool create_dhcp_server --tool-args '{"name": "dhcp-vlan100", "interface": "vlan100", "address_pool": "pool-vlan100"}'

# List DHCP servers
uv run mcp-cli cmd --server mikrotik --tool list_dhcp_servers --tool-args '{}'

# Get DHCP server details
uv run mcp-cli cmd --server mikrotik --tool get_dhcp_server --tool-args '{"name": "dhcp-vlan100"}'

# Remove DHCP server
uv run mcp-cli cmd --server mikrotik --tool remove_dhcp_server --tool-args '{"name": "dhcp-vlan100"}'
```

### NAT Rule Management
```bash
# Create masquerade rule
uv run mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "srcnat", "action": "masquerade", "out_interface": "ether1", "comment": "Internet access"}'

# Create port forwarding rule
uv run mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "dstnat", "action": "dst-nat", "dst_port": "80", "protocol": "tcp", "to_addresses": "192.168.100.10", "to_ports": "80", "comment": "Web server"}'

# List NAT rules
uv run mcp-cli cmd --server mikrotik --tool list_nat_rules --tool-args '{"chain_filter": "srcnat"}'

# Get NAT rule details
uv run mcp-cli cmd --server mikrotik --tool get_nat_rule --tool-args '{"rule_id": "*1"}'

# Move NAT rule
uv run mcp-cli cmd --server mikrotik --tool move_nat_rule --tool-args '{"rule_id": "*1", "destination": 0}'

# Enable/Disable NAT rule
uv run mcp-cli cmd --server mikrotik --tool disable_nat_rule --tool-args '{"rule_id": "*1"}'
uv run mcp-cli cmd --server mikrotik --tool enable_nat_rule --tool-args '{"rule_id": "*1"}'

# Remove NAT rule
uv run mcp-cli cmd --server mikrotik --tool remove_nat_rule --tool-args '{"rule_id": "*1"}'
```

### IP Pool Management
```bash
# Create IP pool
uv run mcp-cli cmd --server mikrotik --tool create_ip_pool --tool-args '{"name": "main-pool", "ranges": "192.168.1.100-192.168.1.200"}'

# List IP pools
uv run mcp-cli cmd --server mikrotik --tool list_ip_pools --tool-args '{"include_used": true}'

# Get IP pool details
uv run mcp-cli cmd --server mikrotik --tool get_ip_pool --tool-args '{"name": "main-pool"}'

# List used addresses in pool
uv run mcp-cli cmd --server mikrotik --tool list_ip_pool_used --tool-args '{"pool_name": "main-pool"}'

# Expand IP pool
uv run mcp-cli cmd --server mikrotik --tool expand_ip_pool --tool-args '{"name": "main-pool", "additional_ranges": "192.168.1.201-192.168.1.250"}'

# Remove IP pool
uv run mcp-cli cmd --server mikrotik --tool remove_ip_pool --tool-args '{"name": "main-pool"}'
```

### Backup and Export
```bash
# Create system backup
uv run mcp-cli cmd --server mikrotik --tool create_backup --tool-args '{"name": "full_backup", "include_password": true}'

# Create configuration export
uv run mcp-cli cmd --server mikrotik --tool create_export --tool-args '{"name": "config_export", "file_format": "rsc", "export_type": "full"}'

# Export specific section
uv run mcp-cli cmd --server mikrotik --tool export_section --tool-args '{"section": "/ip/firewall", "name": "firewall_export"}'

# List backups
uv run mcp-cli cmd --server mikrotik --tool list_backups --tool-args '{"include_exports": true}'

# Download file
uv run mcp-cli cmd --server mikrotik --tool download_file --tool-args '{"filename": "full_backup.backup"}'

# Upload file
uv run mcp-cli cmd --server mikrotik --tool upload_file --tool-args '{"filename": "config.rsc", "content_base64": "base64_encoded_content"}'

# Restore backup
uv run mcp-cli cmd --server mikrotik --tool restore_backup --tool-args '{"filename": "full_backup.backup"}'

# Import configuration
uv run mcp-cli cmd --server mikrotik --tool import_configuration --tool-args '{"filename": "config.rsc"}'

# Remove file
uv run mcp-cli cmd --server mikrotik --tool remove_file --tool-args '{"filename": "old_backup.backup"}'
```

### Log Management
```bash
# Get logs
uv run mcp-cli cmd --server mikrotik --tool get_logs --tool-args '{"topics": "firewall", "limit": 100}'

# Get logs by severity
uv run mcp-cli cmd --server mikrotik --tool get_logs_by_severity --tool-args '{"severity": "error", "limit": 50}'

# Search logs
uv run mcp-cli cmd --server mikrotik --tool search_logs --tool-args '{"search_term": "login failed", "case_sensitive": false}'

# Get security logs
uv run mcp-cli cmd --server mikrotik --tool get_security_logs --tool-args '{"limit": 100}'

# Get log statistics
uv run mcp-cli cmd --server mikrotik --tool get_log_statistics --tool-args '{}'

# Export logs
uv run mcp-cli cmd --server mikrotik --tool export_logs --tool-args '{"filename": "firewall_logs", "topics": "firewall", "format": "csv"}'

# Monitor logs
uv run mcp-cli cmd --server mikrotik --tool monitor_logs --tool-args '{"topics": "firewall", "duration": 30}'

# Clear logs
uv run mcp-cli cmd --server mikrotik --tool clear_logs --tool-args '{}'
```

### Firewall Filter Rules
```bash
# Create basic firewall rules
uv run mcp-cli cmd --server mikrotik --tool create_filter_rule --tool-args '{"chain": "input", "action": "accept", "connection_state": "established,related", "comment": "Accept established"}'
uv run mcp-cli cmd --server mikrotik --tool create_filter_rule --tool-args '{"chain": "input", "action": "drop", "connection_state": "invalid", "comment": "Drop invalid"}'
uv run mcp-cli cmd --server mikrotik --tool create_filter_rule --tool-args '{"chain": "input", "action": "accept", "protocol": "icmp", "comment": "Accept ICMP"}'

# List firewall rules
uv run mcp-cli cmd --server mikrotik --tool list_filter_rules --tool-args '{"chain_filter": "input"}'

# Get firewall rule details
uv run mcp-cli cmd --server mikrotik --tool get_filter_rule --tool-args '{"rule_id": "*1"}'

# Move firewall rule
uv run mcp-cli cmd --server mikrotik --tool move_filter_rule --tool-args '{"rule_id": "*1", "destination": 0}'

# Enable/Disable firewall rule
uv run mcp-cli cmd --server mikrotik --tool disable_filter_rule --tool-args '{"rule_id": "*1"}'
uv run mcp-cli cmd --server mikrotik --tool enable_filter_rule --tool-args '{"rule_id": "*1"}'

# Create basic firewall setup
uv run mcp-cli cmd --server mikrotik --tool create_basic_firewall_setup --tool-args '{}'

# Remove firewall rule
uv run mcp-cli cmd --server mikrotik --tool remove_filter_rule --tool-args '{"rule_id": "*1"}'
```

### Route Management
```bash
# Add route
uv run mcp-cli cmd --server mikrotik --tool add_route --tool-args '{"dst_address": "10.0.0.0/8", "gateway": "192.168.1.1", "comment": "Corporate network"}'

# Add default route
uv run mcp-cli cmd --server mikrotik --tool add_default_route --tool-args '{"gateway": "192.168.1.1", "distance": 1}'

# Add blackhole route
uv run mcp-cli cmd --server mikrotik --tool add_blackhole_route --tool-args '{"dst_address": "192.168.99.0/24", "comment": "Block subnet"}'

# List routes
uv run mcp-cli cmd --server mikrotik --tool list_routes --tool-args '{"active_only": true}'

# Get route details
uv run mcp-cli cmd --server mikrotik --tool get_route --tool-args '{"route_id": "*1"}'

# Check route path
uv run mcp-cli cmd --server mikrotik --tool check_route_path --tool-args '{"destination": "8.8.8.8"}'

# Get routing table
uv run mcp-cli cmd --server mikrotik --tool get_routing_table --tool-args '{"table_name": "main"}'

# Get route statistics
uv run mcp-cli cmd --server mikrotik --tool get_route_statistics --tool-args '{}'

# Enable/Disable route
uv run mcp-cli cmd --server mikrotik --tool disable_route --tool-args '{"route_id": "*1"}'
uv run mcp-cli cmd --server mikrotik --tool enable_route --tool-args '{"route_id": "*1"}'

# Remove route
uv run mcp-cli cmd --server mikrotik --tool remove_route --tool-args '{"route_id": "*1"}'
```

### DNS Configuration
```bash
# Set DNS servers
uv run mcp-cli cmd --server mikrotik --tool set_dns_servers --tool-args '{"servers": ["8.8.8.8", "8.8.4.4"], "allow_remote_requests": true}'

# Get DNS settings
uv run mcp-cli cmd --server mikrotik --tool get_dns_settings --tool-args '{}'

# Add static DNS entry
uv run mcp-cli cmd --server mikrotik --tool add_dns_static --tool-args '{"name": "router.local", "address": "192.168.1.1", "comment": "Local router"}'

# Add CNAME record
uv run mcp-cli cmd --server mikrotik --tool add_dns_static --tool-args '{"name": "www.example.com", "cname": "example.com"}'

# List static DNS entries
uv run mcp-cli cmd --server mikrotik --tool list_dns_static --tool-args '{"name_filter": "local"}'

# Update DNS entry
uv run mcp-cli cmd --server mikrotik --tool update_dns_static --tool-args '{"entry_id": "*1", "address": "192.168.1.2"}'

# Add DNS regexp
uv run mcp-cli cmd --server mikrotik --tool add_dns_regexp --tool-args '{"regexp": ".*\\.ads\\..*", "address": "0.0.0.0", "comment": "Block ads"}'

# Test DNS query
uv run mcp-cli cmd --server mikrotik --tool test_dns_query --tool-args '{"name": "google.com"}'

# Get DNS cache
uv run mcp-cli cmd --server mikrotik --tool get_dns_cache --tool-args '{}'

# Flush DNS cache
uv run mcp-cli cmd --server mikrotik --tool flush_dns_cache --tool-args '{}'

# Export DNS config
uv run mcp-cli cmd --server mikrotik --tool export_dns_config --tool-args '{"filename": "dns_config"}'

# Remove DNS entry
uv run mcp-cli cmd --server mikrotik --tool remove_dns_static --tool-args '{"entry_id": "*1"}'
```

### User Management
```bash
# Add user
uv run mcp-cli cmd --server mikrotik --tool add_user --tool-args '{"name": "newuser", "password": "SecurePass123", "group": "write", "comment": "New operator"}'

# List users
uv run mcp-cli cmd --server mikrotik --tool list_users --tool-args '{"group_filter": "write"}'

# Get user details
uv run mcp-cli cmd --server mikrotik --tool get_user --tool-args '{"name": "newuser"}'

# Update user
uv run mcp-cli cmd --server mikrotik --tool update_user --tool-args '{"name": "newuser", "password": "NewSecurePass456"}'

# Enable/Disable user
uv run mcp-cli cmd --server mikrotik --tool disable_user --tool-args '{"name": "newuser"}'
uv run mcp-cli cmd --server mikrotik --tool enable_user --tool-args '{"name": "newuser"}'

# Add user group
uv run mcp-cli cmd --server mikrotik --tool add_user_group --tool-args '{"name": "operators", "policy": ["read", "write", "test"], "comment": "Operator group"}'

# List user groups
uv run mcp-cli cmd --server mikrotik --tool list_user_groups --tool-args '{}'

# Get active users
uv run mcp-cli cmd --server mikrotik --tool get_active_users --tool-args '{}'

# Export user config
uv run mcp-cli cmd --server mikrotik --tool export_user_config --tool-args '{"filename": "user_config"}'

# Remove user
uv run mcp-cli cmd --server mikrotik --tool remove_user --tool-args '{"name": "newuser"}'
```

#### Setting Up a New Network Segment
```bash
# Create VLAN
uv run mcp-cli cmd --server mikrotik --tool create_vlan_interface --tool-args '{"name": "vlan200", "vlan_id": 200, "interface": "ether1", "comment": "Guest Network"}'

# Add IP address
uv run mcp-cli cmd --server mikrotik --tool add_ip_address --tool-args '{"address": "192.168.200.1/24", "interface": "vlan200"}'

# Create DHCP pool
uv run mcp-cli cmd --server mikrotik --tool create_dhcp_pool --tool-args '{"name": "pool-200", "ranges": "192.168.200.10-192.168.200.100"}'

# Create DHCP network
uv run mcp-cli cmd --server mikrotik --tool create_dhcp_network --tool-args '{"network": "192.168.200.0/24", "gateway": "192.168.200.1", "dns_servers": ["8.8.8.8", "8.8.4.4"]}'

# Create DHCP server
uv run mcp-cli cmd --server mikrotik --tool create_dhcp_server --tool-args '{"name": "dhcp-200", "interface": "vlan200", "address_pool": "pool-200"}'

# Create NAT rule
uv run mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "srcnat", "action": "masquerade", "out_interface": "ether1", "comment": "Internet access for VLAN 200"}'
```

#### Port Forwarding Setup
```bash
# Forward HTTP traffic
uv run mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "dstnat", "action": "dst-nat", "dst_address": "203.0.113.1", "dst_port": "80", "protocol": "tcp", "to_addresses": "192.168.100.10", "to_ports": "80", "comment": "Web server"}'

# Forward HTTPS traffic
uv run mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "dstnat", "action": "dst-nat", "dst_address": "203.0.113.1", "dst_port": "443", "protocol": "tcp", "to_addresses": "192.168.100.10", "to_ports": "443", "comment": "HTTPS server"}'

# Forward custom SSH port
uv run mcp-cli cmd --server mikrotik --tool create_nat_rule --tool-args '{"chain": "dstnat", "action": "dst-nat", "dst_address": "203.0.113.1", "dst_port": "2222", "protocol": "tcp", "to_addresses": "192.168.100.10", "to_ports": "22", "comment": "SSH server"}'
```

#### Backup and Restore Process
```bash
# Create backup user
uv run mcp-cli cmd --server mikrotik --tool add_user --tool-args '{"name": "backup_user", "password": "BackupPass123", "group": "read", "comment": "Backup account"}'

# Create full backup
uv run mcp-cli cmd --server mikrotik --tool create_backup --tool-args '{"name": "daily_backup", "include_password": true}'

# Export configuration
uv run mcp-cli cmd --server mikrotik --tool create_export --tool-args '{"name": "config_export", "file_format": "rsc", "export_type": "full"}'

# Export firewall rules
uv run mcp-cli cmd --server mikrotik --tool export_section --tool-args '{"section": "/ip/firewall/filter", "name": "firewall_backup"}'

# Export NAT rules
uv run mcp-cli cmd --server mikrotik --tool export_section --tool-args '{"section": "/ip/firewall/nat", "name": "nat_backup"}'
```

### Create Wireless Interface
```bash
# Create basic AP interface
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wlan1", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "MyNetwork", "comment": "Main WiFi Network"}'

# Create station interface
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wlan-sta", "radio_name": "wlan2", "mode": "station", "ssid": "UpstreamWiFi"}'

# Create with specific frequency and band
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wlan-5g", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "MyNetwork-5G", "frequency": "5180", "band": "5ghz-a/n/ac", "channel_width": "80mhz"}'
```

### List and Manage Wireless Interfaces
```bash
# List all wireless interfaces
uv run mcp-cli cmd --server mikrotik --tool list_wireless_interfaces --tool-args '{}'

# List only AP interfaces
uv run mcp-cli cmd --server mikrotik --tool list_wireless_interfaces --tool-args '{"mode_filter": "ap-bridge"}'

# List only running interfaces
uv run mcp-cli cmd --server mikrotik --tool list_wireless_interfaces --tool-args '{"running_only": true}'

# Get specific interface details
uv run mcp-cli cmd --server mikrotik --tool get_wireless_interface --tool-args '{"name": "wlan1"}'

# Update wireless interface
uv run mcp-cli cmd --server mikrotik --tool update_wireless_interface --tool-args '{"name": "wlan1", "ssid": "UpdatedNetworkName", "comment": "Updated main network"}'

# Enable/Disable wireless interface
uv run mcp-cli cmd --server mikrotik --tool disable_wireless_interface --tool-args '{"name": "wlan1"}'
uv run mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "wlan1"}'

# Remove wireless interface
uv run mcp-cli cmd --server mikrotik --tool remove_wireless_interface --tool-args '{"name": "wlan-guest"}'
```

## Wireless Security Profile Management

### Create Security Profiles
```bash
# Create WPA2-PSK security profile
uv run mcp-cli cmd --server mikrotik --tool create_wireless_security_profile --tool-args '{"name": "wpa2-security", "mode": "dynamic-keys", "authentication_types": ["wpa2-psk"], "unicast_ciphers": ["aes-ccm"], "group_ciphers": ["aes-ccm"], "wpa2_pre_shared_key": "SecurePassword123"}'

# Create mixed WPA/WPA2 profile
uv run mcp-cli cmd --server mikrotik --tool create_wireless_security_profile --tool-args '{"name": "mixed-security", "mode": "dynamic-keys", "authentication_types": ["wpa-psk", "wpa2-psk"], "unicast_ciphers": ["tkip", "aes-ccm"], "group_ciphers": ["tkip"], "wpa_pre_shared_key": "Password123", "wpa2_pre_shared_key": "Password123"}'

# Create WPA2-Enterprise profile
uv run mcp-cli cmd --server mikrotik --tool create_wireless_security_profile --tool-args '{"name": "enterprise-security", "mode": "dynamic-keys", "authentication_types": ["wpa2-eap"], "unicast_ciphers": ["aes-ccm"], "group_ciphers": ["aes-ccm"], "eap_methods": "peap,tls"}'

# Create open network profile
uv run mcp-cli cmd --server mikrotik --tool create_wireless_security_profile --tool-args '{"name": "open-network", "mode": "none", "comment": "Guest network - no security"}'
```

### Manage Security Profiles
```bash
# List all security profiles
uv run mcp-cli cmd --server mikrotik --tool list_wireless_security_profiles --tool-args '{}'

# List WPA2 profiles only
uv run mcp-cli cmd --server mikrotik --tool list_wireless_security_profiles --tool-args '{"mode_filter": "dynamic-keys"}'

# Get specific profile details
uv run mcp-cli cmd --server mikrotik --tool get_wireless_security_profile --tool-args '{"name": "wpa2-security"}'

# Apply security profile to interface
uv run mcp-cli cmd --server mikrotik --tool set_wireless_security_profile --tool-args '{"interface_name": "wlan1", "security_profile": "wpa2-security"}'

# Remove security profile
uv run mcp-cli cmd --server mikrotik --tool remove_wireless_security_profile --tool-args '{"name": "old-profile"}'
```

## Wireless Network Operations

### Network Scanning and Monitoring
```bash
# Scan for available networks
uv run mcp-cli cmd --server mikrotik --tool scan_wireless_networks --tool-args '{"interface": "wlan1", "duration": 10}'

# Quick scan (5 seconds)
uv run mcp-cli cmd --server mikrotik --tool scan_wireless_networks --tool-args '{"interface": "wlan2"}'

# Get connected clients (all interfaces)
uv run mcp-cli cmd --server mikrotik --tool get_wireless_registration_table --tool-args '{}'

# Get clients for specific interface
uv run mcp-cli cmd --server mikrotik --tool get_wireless_registration_table --tool-args '{"interface": "wlan1"}'
```

## Wireless Access List Management

### Create Access List Entries
```bash
# Allow specific MAC address
uv run mcp-cli cmd --server mikrotik --tool create_wireless_access_list --tool-args '{"interface": "wlan1", "mac_address": "AA:BB:CC:DD:EE:FF", "action": "accept", "comment": "Trusted device"}'

# Block specific MAC address
uv run mcp-cli cmd --server mikrotik --tool create_wireless_access_list --tool-args '{"interface": "wlan1", "mac_address": "11:22:33:44:55:66", "action": "reject", "comment": "Blocked device"}'

# Allow with signal strength requirement
uv run mcp-cli cmd --server mikrotik --tool create_wireless_access_list --tool-args '{"interface": "wlan1", "mac_address": "AA:BB:CC:DD:EE:FF", "action": "accept", "signal_range": "-80..-50", "comment": "Strong signal only"}'

# Time-based access control
uv run mcp-cli cmd --server mikrotik --tool create_wireless_access_list --tool-args '{"interface": "wlan1", "mac_address": "AA:BB:CC:DD:EE:FF", "action": "accept", "time": "8h-18h,mon,tue,wed,thu,fri", "comment": "Work hours only"}'
```

### Manage Access Lists
```bash
# List all access list entries
uv run mcp-cli cmd --server mikrotik --tool list_wireless_access_list --tool-args '{}'

# List entries for specific interface
uv run mcp-cli cmd --server mikrotik --tool list_wireless_access_list --tool-args '{"interface_filter": "wlan1"}'

# List only blocked entries
uv run mcp-cli cmd --server mikrotik --tool list_wireless_access_list --tool-args '{"action_filter": "reject"}'

# Remove access list entry
uv run mcp-cli cmd --server mikrotik --tool remove_wireless_access_list_entry --tool-args '{"entry_id": "*1"}'
```

## Complete WiFi Network Setup Examples

### Basic Home Network Setup
```bash
# 1. Create security profile
uv run mcp-cli cmd --server mikrotik --tool create_wireless_security_profile --tool-args '{"name": "home-security", "mode": "dynamic-keys", "authentication_types": ["wpa2-psk"], "unicast_ciphers": ["aes-ccm"], "group_ciphers": ["aes-ccm"], "wpa2_pre_shared_key": "MyHomePassword123"}'

# 2. Create wireless interface
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "home-wifi", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "HomeNetwork", "band": "2ghz-b/g/n", "comment": "Main home network"}'

# 3. Apply security profile
uv run mcp-cli cmd --server mikrotik --tool set_wireless_security_profile --tool-args '{"interface_name": "home-wifi", "security_profile": "home-security"}'

# 4. Enable the interface
uv run mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "home-wifi"}'
```

### Guest Network Setup
```bash
# 1. Create open security profile for guests
uv run mcp-cli cmd --server mikrotik --tool create_wireless_security_profile --tool-args '{"name": "guest-open", "mode": "none", "comment": "Open guest network"}'

# 2. Create guest wireless interface
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "guest-wifi", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "GuestNetwork", "comment": "Guest access network"}'

# 3. Apply open security profile
uv run mcp-cli cmd --server mikrotik --tool set_wireless_security_profile --tool-args '{"interface_name": "guest-wifi", "security_profile": "guest-open"}'

# 4. Enable guest network
uv run mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "guest-wifi"}'
```

### Enterprise Network Setup
```bash
# 1. Create WPA2-Enterprise security profile
uv run mcp-cli cmd --server mikrotik --tool create_wireless_security_profile --tool-args '{"name": "corp-security", "mode": "dynamic-keys", "authentication_types": ["wpa2-eap"], "unicast_ciphers": ["aes-ccm"], "group_ciphers": ["aes-ccm"], "eap_methods": "peap", "comment": "Corporate WPA2-Enterprise"}'

# 2. Create corporate wireless interface
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "corp-wifi", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "CorpNetwork", "band": "5ghz-a/n/ac", "channel_width": "80mhz", "comment": "Corporate network"}'

# 3. Apply enterprise security
uv run mcp-cli cmd --server mikrotik --tool set_wireless_security_profile --tool-args '{"interface_name": "corp-wifi", "security_profile": "corp-security"}'

# 4. Create access control for specific devices
uv run mcp-cli cmd --server mikrotik --tool create_wireless_access_list --tool-args '{"interface": "corp-wifi", "mac_address": "00:11:22:33:44:55", "action": "accept", "comment": "Corporate laptop"}'
```

### Dual-Band Setup (2.4GHz + 5GHz)
```bash
# 1. Create security profile
uv run mcp-cli cmd --server mikrotik --tool create_wireless_security_profile --tool-args '{"name": "dual-band-security", "mode": "dynamic-keys", "authentication_types": ["wpa2-psk"], "unicast_ciphers": ["aes-ccm"], "group_ciphers": ["aes-ccm"], "wpa2_pre_shared_key": "DualBandPassword123"}'

# 2. Create 2.4GHz interface
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wifi-2g", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "MyNetwork", "band": "2ghz-b/g/n", "channel_width": "20mhz", "comment": "2.4GHz network"}'

# 3. Create 5GHz interface  
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "wifi-5g", "radio_name": "wlan2", "mode": "ap-bridge", "ssid": "MyNetwork-5G", "band": "5ghz-a/n/ac", "channel_width": "80mhz", "comment": "5GHz network"}'

# 4. Apply security to both interfaces
uv run mcp-cli cmd --server mikrotik --tool set_wireless_security_profile --tool-args '{"interface_name": "wifi-2g", "security_profile": "dual-band-security"}'
uv run mcp-cli cmd --server mikrotik --tool set_wireless_security_profile --tool-args '{"interface_name": "wifi-5g", "security_profile": "dual-band-security"}'

# 5. Enable both interfaces
uv run mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "wifi-2g"}'
uv run mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "wifi-5g"}'
```

### Point-to-Point Wireless Link
```bash
# On first device (Station)
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "p2p-station", "radio_name": "wlan1", "mode": "station", "ssid": "P2P-Link", "frequency": "5180", "band": "5ghz-a/n"}'

# On second device (AP)  
uv run mcp-cli cmd --server mikrotik --tool create_wireless_interface --tool-args '{"name": "p2p-ap", "radio_name": "wlan1", "mode": "ap-bridge", "ssid": "P2P-Link", "frequency": "5180", "band": "5ghz-a/n"}'

# Create security for P2P link
uv run mcp-cli cmd --server mikrotik --tool create_wireless_security_profile --tool-args '{"name": "p2p-security", "mode": "dynamic-keys", "authentication_types": ["wpa2-psk"], "unicast_ciphers": ["aes-ccm"], "group_ciphers": ["aes-ccm"], "wpa2_pre_shared_key": "P2PLinkPassword123"}'

# Apply security to both ends
uv run mcp-cli cmd --server mikrotik --tool set_wireless_security_profile --tool-args '{"interface_name": "p2p-station", "security_profile": "p2p-security"}'
uv run mcp-cli cmd --server mikrotik --tool set_wireless_security_profile --tool-args '{"interface_name": "p2p-ap", "security_profile": "p2p-security"}'
```

## Monitoring and Troubleshooting

### Network Analysis
```bash
# Scan for interference and available channels
uv run mcp-cli cmd --server mikrotik --tool scan_wireless_networks --tool-args '{"interface": "wlan1", "duration": 30}'

# Monitor connected clients
uv run mcp-cli cmd --server mikrotik --tool get_wireless_registration_table --tool-args '{"interface": "wlan1"}'

# Check interface status
uv run mcp-cli cmd --server mikrotik --tool get_wireless_interface --tool-args '{"name": "wlan1"}'

# List all wireless configurations
uv run mcp-cli cmd --server mikrotik --tool list_wireless_interfaces --tool-args '{}'
uv run mcp-cli cmd --server mikrotik --tool list_wireless_security_profiles --tool-args '{}'
uv run mcp-cli cmd --server mikrotik --tool list_wireless_access_list --tool-args '{}'
```

### Maintenance Operations
```bash
# Disable interface for maintenance
uv run mcp-cli cmd --server mikrotik --tool disable_wireless_interface --tool-args '{"name": "wlan1"}'

# Update configuration
uv run mcp-cli cmd --server mikrotik --tool update_wireless_interface --tool-args '{"name": "wlan1", "channel_width": "40mhz", "comment": "Updated for better performance"}'

# Re-enable interface
uv run mcp-cli cmd --server mikrotik --tool enable_wireless_interface --tool-args '{"name": "wlan1"}'

# Clean up unused profiles
uv run mcp-cli cmd --server mikrotik --tool remove_wireless_security_profile --tool-args '{"name": "old-profile"}'
```

# Using MCPO with MikroTik MCP Server

This guide shows how to expose your MikroTik MCP server as a RESTful API using MCPO (MCP-to-OpenAPI proxy).
