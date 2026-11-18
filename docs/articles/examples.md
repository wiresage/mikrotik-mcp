# MikroTik MCP - 25 Practical Examples

This guide provides practical examples for developers learning to interact with MikroTik devices using the MCP (Model Context Protocol) tools.

---

## Example 1: Create a Guest Network with VLAN

**Prompt to AI**:
```
Create a new VLAN 200 for the guest network on ether1, assign IP 192.168.200.1/24, 
set up DHCP from .10 to .250, and add a masquerade NAT rule for internet access.
```

**What AI Will Do**:
1. Create VLAN 200 interface on ether1 with name "vlan200-guest"
2. Assign IP address 192.168.200.1/24 to the VLAN interface
3. Create an IP pool named "guest-pool" with range 192.168.200.10-250
4. Create DHCP network configuration with gateway and DNS servers
5. Create and enable DHCP server on the VLAN interface
6. Add masquerade NAT rule for internet access through ether1

**Manual Commands**:
```bash
/interface vlan add name=vlan200-guest vlan-id=200 interface=ether1 comment="Guest Network"
/ip address add address=192.168.200.1/24 interface=vlan200-guest
/ip pool add name=guest-pool ranges=192.168.200.10-192.168.200.250
/ip dhcp-server network add address=192.168.200.0/24 gateway=192.168.200.1 dns-server=8.8.8.8,8.8.4.4
/ip dhcp-server add name=dhcp-guest interface=vlan200-guest address-pool=guest-pool lease-time=1h
/ip firewall nat add chain=srcnat action=masquerade src-address=192.168.200.0/24 out-interface=ether1
```

---

## Example 2: Create IoT Network with VLAN 50

**Prompt to AI**:
```
Set up an IoT network on VLAN 50 using the bridge interface. Assign IP 192.168.50.1/24, 
create DHCP server with range .10 to .200 and 24-hour lease time. Add firewall rules to 
block IoT devices from accessing the main LAN (192.168.1.0/24) but allow internet access.
```

**What AI Will Do**:
1. Create VLAN 50 interface on bridge with name "vlan50-iot"
2. Assign IP address 192.168.50.1/24 to the VLAN interface
3. Create IP pool "iot-pool" with range 192.168.50.10-200
4. Configure DHCP network with local DNS server
5. Create DHCP server with 24-hour lease time
6. Add firewall filter rule to drop traffic from IoT to LAN subnet
7. Add masquerade NAT rule for internet access

**Manual Commands**:
```bash
/interface vlan add name=vlan50-iot vlan-id=50 interface=bridge comment="IoT Devices"
/ip address add address=192.168.50.1/24 interface=vlan50-iot
/ip pool add name=iot-pool ranges=192.168.50.10-192.168.50.200
/ip dhcp-server network add address=192.168.50.0/24 gateway=192.168.50.1 dns-server=192.168.50.1
/ip dhcp-server add name=dhcp-iot interface=vlan50-iot address-pool=iot-pool lease-time=24h
/ip firewall filter add chain=forward src-address=192.168.50.0/24 dst-address=192.168.1.0/24 action=drop comment="Block IoT to LAN"
/ip firewall nat add chain=srcnat src-address=192.168.50.0/24 out-interface=ether1 action=masquerade
```

---

## Example 3: Port Forwarding for Web Server

**Prompt to AI**:
```
Configure port forwarding to redirect incoming HTTP (port 80) and HTTPS (port 443) 
traffic from ether1 to my internal web server at 192.168.1.100. Also add firewall 
rules to allow this forwarded traffic.
```

**What AI Will Do**:
1. Create destination NAT rule for port 80 (HTTP) forwarding to 192.168.1.100
2. Create destination NAT rule for port 443 (HTTPS) forwarding to 192.168.1.100
3. Add firewall filter rules to accept forwarded traffic to the web server on ports 80 and 443
4. Properly configure both dst-nat and forward chain rules

**Manual Commands**:
```bash
/ip firewall nat add chain=dstnat protocol=tcp dst-port=80 in-interface=ether1 action=dst-nat to-addresses=192.168.1.100 to-ports=80 comment="HTTP to Web Server"
/ip firewall nat add chain=dstnat protocol=tcp dst-port=443 in-interface=ether1 action=dst-nat to-addresses=192.168.1.100 to-ports=443 comment="HTTPS to Web Server"
/ip firewall filter add chain=forward protocol=tcp dst-address=192.168.1.100 dst-port=80,443 action=accept comment="Allow Web Server Traffic"
```

---

## Example 4: Basic Firewall Protection

**Prompt to AI**:
```
Set up basic firewall security rules for my router. Accept established and related 
connections, drop invalid packets, allow ICMP ping, allow SSH access from WAN on port 22, 
and drop all other incoming WAN traffic. Also configure similar rules for forwarded traffic.
```

**What AI Will Do**:
1. Create input chain rule to accept established/related connections
2. Create rule to drop invalid connection states
3. Add rule to allow ICMP (ping) protocol
4. Add rule to allow SSH (TCP port 22) from WAN interface
5. Add default drop rule for all other WAN input traffic
6. Create corresponding forward chain rules for established/related and invalid connections
7. Order rules properly for optimal firewall performance

**Manual Commands**:
```bash
/ip firewall filter add chain=input connection-state=established,related action=accept comment="Accept Established/Related"
/ip firewall filter add chain=input connection-state=invalid action=drop comment="Drop Invalid"
/ip firewall filter add chain=input protocol=icmp action=accept comment="Allow ICMP"
/ip firewall filter add chain=input in-interface=ether1 protocol=tcp dst-port=22 action=accept comment="Allow SSH from WAN"
/ip firewall filter add chain=input in-interface=ether1 action=drop comment="Drop All Other WAN Input"
/ip firewall filter add chain=forward connection-state=established,related action=accept
/ip firewall filter add chain=forward connection-state=invalid action=drop
```

---

## Example 5: VPN Server VLAN Setup

**Scenario**: Create dedicated VLAN 100 for VPN clients.

**Manual Commands**:
```bash
/interface vlan add name=vlan100-vpn vlan-id=100 interface=bridge comment="VPN Clients"
/ip address add address=10.10.100.1/24 interface=vlan100-vpn
/ip pool add name=vpn-pool ranges=10.10.100.10-10.10.100.250
/ip dhcp-server network add address=10.10.100.0/24 gateway=10.10.100.1 dns-server=8.8.8.8
/ip dhcp-server add name=dhcp-vpn interface=vlan100-vpn address-pool=vpn-pool lease-time=8h
/ip firewall nat add chain=srcnat src-address=10.10.100.0/24 action=masquerade comment="VPN Internet Access"
```

---

## Example 6: Management VLAN

**Prompt to AI**:
```
Set up a secure management network on VLAN 10 using the bridge. Assign 192.168.10.1/24 
as the gateway, create DHCP for range .10 to .50 with 4-hour leases, and add a firewall 
rule to allow all traffic from this management subnet to access the router.
```

**What AI Will Do**:
1. Create VLAN 10 interface on bridge with name "vlan10-mgmt"
2. Assign IP address 192.168.10.1/24 to the management VLAN
3. Create IP pool "mgmt-pool" with limited range (.10-.50) for administrators
4. Configure DHCP network with local DNS server (192.168.10.1)
5. Create DHCP server with 4-hour lease time
6. Add firewall filter rule in input chain to accept all traffic from management subnet
7. Ensure proper commenting for security auditing

**Manual Commands**:
```bash
/interface vlan add name=vlan10-mgmt vlan-id=10 interface=bridge comment="Management Network"
/ip address add address=192.168.10.1/24 interface=vlan10-mgmt
/ip pool add name=mgmt-pool ranges=192.168.10.10-192.168.10.50
/ip dhcp-server network add address=192.168.10.0/24 gateway=192.168.10.1 dns-server=192.168.10.1
/ip dhcp-server add name=dhcp-mgmt interface=vlan10-mgmt address-pool=mgmt-pool lease-time=4h
/ip firewall filter add chain=input src-address=192.168.10.0/24 action=accept comment="Allow Management Access"
```

---

## Example 7: DNS Configuration with DoH

**Prompt to AI**:
```
Configure the router to use Cloudflare DNS servers (1.1.1.1 and 1.0.0.1) with 
DNS-over-HTTPS enabled for privacy. Set cache size to 4096 KiB, allow remote DNS 
requests, and add static DNS entries for router.local pointing to 192.168.1.1 
and nas.local pointing to 192.168.1.10.
```

**What AI Will Do**:
1. Set primary and secondary DNS servers to Cloudflare (1.1.1.1, 1.0.0.1)
2. Enable remote DNS request handling
3. Configure DNS cache size to 4096 KiB
4. Enable DNS-over-HTTPS using Cloudflare's DoH server
5. Enable certificate verification for DoH
6. Add static DNS entry for "router.local" → 192.168.1.1
7. Add static DNS entry for "nas.local" → 192.168.1.10
8. Add appropriate comments for each static entry

**Manual Commands**:
```bash
/ip dns set servers=1.1.1.1,1.0.0.1 allow-remote-requests=yes cache-size=4096KiB
/ip dns set use-doh-server=https://cloudflare-dns.com/dns-query verify-doh-cert=yes
/ip dns static add name=router.local address=192.168.1.1 comment="Router Local DNS"
/ip dns static add name=nas.local address=192.168.1.10 comment="NAS Device"
```

---

## Example 8: Static Routes for Multiple Subnets

**Prompt to AI**:
```
Add static routes for my network: route traffic to 192.168.20.0/24 via gateway 
192.168.1.254, route 192.168.30.0/24 via 192.168.1.253, route 10.0.0.0/8 via 
192.168.1.252 with distance 10, and set default route to 192.168.1.1 with distance 1.
```

**What AI Will Do**:
1. Create static route for subnet 192.168.20.0/24 via gateway 192.168.1.254
2. Create static route for subnet 192.168.30.0/24 via gateway 192.168.1.253
3. Create static route for large private network 10.0.0.0/8 via 192.168.1.252 with custom distance
4. Create default route (0.0.0.0/0) via 192.168.1.1 with distance 1
5. Add descriptive comments for each route
6. Ensure proper route priority using distance values

**Manual Commands**:
```bash
/ip route add dst-address=192.168.20.0/24 gateway=192.168.1.254 comment="Route to Subnet 20"
/ip route add dst-address=192.168.30.0/24 gateway=192.168.1.253 comment="Route to Subnet 30"
/ip route add dst-address=10.0.0.0/8 gateway=192.168.1.252 distance=10 comment="Route to Private Network"
/ip route add dst-address=0.0.0.0/0 gateway=192.168.1.1 distance=1 comment="Default Route"
```

---

## Example 9: Rate Limiting for Guest Network

**Prompt to AI**:
```
Limit bandwidth for my guest network (192.168.200.0/24) to prevent abuse. 
Set maximum download speed to 10 Mbps and upload speed to 5 Mbps using queue 
rules, and ensure guest traffic is allowed through the firewall.
```

**What AI Will Do**:
1. Create simple queue named "guest-download" targeting 192.168.200.0/24
2. Set maximum download limit to 10M/10M (10 Mbps)
3. Create simple queue named "guest-upload" targeting 192.168.200.0/24
4. Set maximum upload limit to 5M/5M (5 Mbps)
5. Add firewall filter rule to accept forwarded traffic from guest network
6. Add descriptive comments for bandwidth management

**Manual Commands**:
```bash
/queue simple add name=guest-download target=192.168.200.0/24 dst=0.0.0.0/0 max-limit=10M/10M comment="Guest Network Limit"
/queue simple add name=guest-upload target=192.168.200.0/24 dst=0.0.0.0/0 max-limit=5M/5M comment="Guest Upload Limit"
/ip firewall filter add chain=forward src-address=192.168.200.0/24 action=accept comment="Allow Guest Forward"
```

---

## Example 10: Block Specific Websites

**Prompt to AI**:
```
Block access to social media websites including facebook.com, twitter.com, and 
instagram.com. Create an address list called "blocked-sites" and add a firewall 
rule to reject traffic to these sites with an ICMP network unreachable message.
```

**What AI Will Do**:
1. Create firewall address-list named "blocked-sites"
2. Add facebook.com to the blocked-sites list
3. Add twitter.com to the blocked-sites list
4. Add instagram.com to the blocked-sites list
5. Create firewall filter rule in forward chain
6. Configure rule to reject traffic matching dst-address-list=blocked-sites
7. Set reject-with to icmp-network-unreachable for proper client notification
8. Add descriptive comment "Block Social Media"

**Manual Commands**:
```bash
/ip firewall address-list add list=blocked-sites address=facebook.com comment="Block Facebook"
/ip firewall address-list add list=blocked-sites address=twitter.com comment="Block Twitter"
/ip firewall address-list add list=blocked-sites address=instagram.com comment="Block Instagram"
/ip firewall filter add chain=forward dst-address-list=blocked-sites action=reject reject-with=icmp-network-unreachable comment="Block Social Media"
```

---

## Example 11: Wireless Access Point Configuration

**Prompt to AI**:
```
Configure wlan1 as an access point with SSID "MyNetwork" using WPA2-PSK security. 
Set the password to "YourStrongPassword123", use 2.4GHz band with b/g/n support, 
set channel width to 20/40MHz-Ce, configure country to US, and enable the interface.
```

**What AI Will Do**:
1. Create wireless security profile named "secure-wifi"
2. Set authentication type to WPA2-PSK with dynamic keys
3. Configure pre-shared key (password) to "YourStrongPassword123"
4. Configure wlan1 interface in AP bridge mode
5. Set SSID to "MyNetwork"
6. Apply the secure-wifi security profile
7. Set frequency to auto with 2.4GHz b/g/n band support
8. Configure channel width to 20/40MHz-Ce
9. Set regulatory country to US
10. Enable the wireless interface (disabled=no)

**Manual Commands**:
```bash
/interface wireless security-profiles add name=secure-wifi authentication-types=wpa2-psk mode=dynamic-keys wpa2-pre-shared-key=YourStrongPassword123
/interface wireless set wlan1 mode=ap-bridge ssid=MyNetwork security-profile=secure-wifi frequency=auto band=2ghz-b/g/n disabled=no
/interface wireless set wlan1 channel-width=20/40mhz-Ce country=us
```

---

## Example 12: DHCP Reservation by MAC Address

**Prompt to AI**:
```
Reserve specific IP addresses for my devices: assign 192.168.1.50 to office printer 
with MAC AA:BB:CC:DD:EE:01, assign 192.168.1.51 to NAS server with MAC 
AA:BB:CC:DD:EE:02, and assign 192.168.1.52 to Security Camera 1 with MAC 
AA:BB:CC:DD:EE:03. Make these leases static.
```

**What AI Will Do**:
1. Create DHCP lease for 192.168.1.50 bound to MAC AA:BB:CC:DD:EE:01
2. Add comment "Office Printer" to first lease
3. Create DHCP lease for 192.168.1.51 bound to MAC AA:BB:CC:DD:EE:02
4. Add comment "NAS Server" to second lease
5. Create DHCP lease for 192.168.1.52 bound to MAC AA:BB:CC:DD:EE:03
6. Add comment "Security Camera 1" to third lease
7. Convert the lease at 192.168.1.50 to static binding
8. Ensure leases persist across reboots

**Manual Commands**:
```bash
/ip dhcp-server lease add address=192.168.1.50 mac-address=AA:BB:CC:DD:EE:01 comment="Office Printer"
/ip dhcp-server lease add address=192.168.1.51 mac-address=AA:BB:CC:DD:EE:02 comment="NAS Server"
/ip dhcp-server lease add address=192.168.1.52 mac-address=AA:BB:CC:DD:EE:03 comment="Security Camera 1"
/ip dhcp-server lease make-static [find address=192.168.1.50]
```

---

## Example 13: Separate VLANs for Departments

**Prompt to AI**:
```
Create isolated networks for three departments on the bridge interface: 
HR department on VLAN 110 with subnet 192.168.110.0/24 and DHCP pool .10-.100, 
Finance department on VLAN 120 with subnet 192.168.120.0/24 and DHCP pool .10-.100, 
IT department on VLAN 130 with subnet 192.168.130.0/24 and DHCP pool .10-.100. 
Each should have its own DHCP server.
```

**What AI Will Do**:
1. Create VLAN 110 interface "vlan110-hr" on bridge
2. Assign IP 192.168.110.1/24 to HR VLAN
3. Create IP pool "hr-pool" with range 192.168.110.10-100
4. Create DHCP server "dhcp-hr" for HR department
5. Create VLAN 120 interface "vlan120-finance" on bridge
6. Assign IP 192.168.120.1/24 to Finance VLAN
7. Create IP pool "finance-pool" with range 192.168.120.10-100
8. Create DHCP server "dhcp-finance" for Finance department
9. Create VLAN 130 interface "vlan130-it" on bridge
10. Assign IP 192.168.130.1/24 to IT VLAN
11. Create IP pool "it-pool" with range 192.168.130.10-100
12. Create DHCP server "dhcp-it" for IT department
13. Configure appropriate DHCP networks for each department

**Manual Commands**:
```bash
# HR Department - VLAN 110
/interface vlan add name=vlan110-hr vlan-id=110 interface=bridge
/ip address add address=192.168.110.1/24 interface=vlan110-hr
/ip pool add name=hr-pool ranges=192.168.110.10-192.168.110.100
/ip dhcp-server add name=dhcp-hr interface=vlan110-hr address-pool=hr-pool

# Finance Department - VLAN 120
/interface vlan add name=vlan120-finance vlan-id=120 interface=bridge
/ip address add address=192.168.120.1/24 interface=vlan120-finance
/ip pool add name=finance-pool ranges=192.168.120.10-192.168.120.100
/ip dhcp-server add name=dhcp-finance interface=vlan120-finance address-pool=finance-pool

# IT Department - VLAN 130
/interface vlan add name=vlan130-it vlan-id=130 interface=bridge
/ip address add address=192.168.130.1/24 interface=vlan130-it
/ip pool add name=it-pool ranges=192.168.130.10-192.168.130.100
/ip dhcp-server add name=dhcp-it interface=vlan130-it address-pool=it-pool
```

---

## Example 14: Time-Based Access Control

**Prompt to AI**:
```
Set up time-based access control for the guest network (192.168.200.0/24). 
Create schedulers to enable guest network access at 8:00 AM and disable it at 
6:00 PM daily. Add a firewall rule that can be toggled by these schedulers.
```

**What AI Will Do**:
1. Create system scheduler named "enable-guest"
2. Set start time to 08:00:00 with 1-day interval
3. Configure script to enable firewall rule with comment "Guest Access"
4. Create system scheduler named "disable-guest"
5. Set start time to 18:00:00 with 1-day interval
6. Configure script to disable firewall rule with comment "Guest Access"
7. Create firewall filter rule in forward chain for source 192.168.200.0/24
8. Set action to accept with comment "Guest Access"
9. Initially create rule as disabled
10. Add appropriate comments to schedulers explaining business hours control

**Manual Commands**:
```bash
/system scheduler add name=enable-guest start-time=08:00:00 interval=1d on-event="/ip firewall filter enable [find comment=\"Guest Access\"]" comment="Enable Guest at 8 AM"
/system scheduler add name=disable-guest start-time=18:00:00 interval=1d on-event="/ip firewall filter disable [find comment=\"Guest Access\"]" comment="Disable Guest at 6 PM"
/ip firewall filter add chain=forward src-address=192.168.200.0/24 action=accept disabled=yes comment="Guest Access"
```

---

## Example 15: Backup Multiple VLANs to Single Gateway

**Prompt to AI**:
```
Configure failover routing with primary gateway at 192.168.1.1 (distance 1) and 
backup gateway at 192.168.1.2 (distance 2). Set up NAT masquerade for three 
networks through ether1: IoT network (192.168.50.0/24), VPN network (192.168.100.0/24), 
and Guest network (192.168.200.0/24).
```

**What AI Will Do**:
1. Create default route (0.0.0.0/0) via primary gateway 192.168.1.1 with distance 1
2. Add comment "Primary Gateway" to first route
3. Create backup default route via secondary gateway 192.168.1.2 with distance 2
4. Add comment "Backup Gateway" to second route
5. Create NAT masquerade rule for IoT subnet (192.168.50.0/24) via ether1
6. Add comment "IoT NAT"
7. Create NAT masquerade rule for VPN subnet (192.168.100.0/24) via ether1
8. Add comment "VPN NAT"
9. Create NAT masquerade rule for Guest subnet (192.168.200.0/24) via ether1
10. Add comment "Guest NAT"
11. Configure automatic failover based on route distance

**Manual Commands**:
```bash
/ip route add dst-address=0.0.0.0/0 gateway=192.168.1.1 distance=1 comment="Primary Gateway"
/ip route add dst-address=0.0.0.0/0 gateway=192.168.1.2 distance=2 comment="Backup Gateway"
/ip firewall nat add chain=srcnat src-address=192.168.50.0/24 out-interface=ether1 action=masquerade comment="IoT NAT"
/ip firewall nat add chain=srcnat src-address=192.168.100.0/24 out-interface=ether1 action=masquerade comment="VPN NAT"
/ip firewall nat add chain=srcnat src-address=192.168.200.0/24 out-interface=ether1 action=masquerade comment="Guest NAT"
```

---

## Example 16: Layer 7 Protocol Filtering

**Prompt to AI**:
```
Block BitTorrent traffic and limit YouTube streaming using Layer 7 filtering. 
Create a layer7 protocol matcher for BitTorrent using the pattern for detecting 
torrent protocol headers, create another matcher for YouTube traffic, then add 
firewall rules to drop BitTorrent completely and limit YouTube to 5 Mbps.
```

**What AI Will Do**:
1. Create Layer 7 protocol named "bittorrent"
2. Configure regex pattern to match BitTorrent protocol signatures
3. Add comment "Block Torrents"
4. Create Layer 7 protocol named "youtube"
5. Configure regex pattern to match YouTube and Google Video domains
6. Add comment "Detect YouTube"
7. Create firewall filter rule in forward chain matching layer7-protocol=bittorrent
8. Set action to drop for BitTorrent traffic
9. Create firewall filter rule in forward chain matching layer7-protocol=youtube
10. Set action to accept with bandwidth limit of 5M/5M for YouTube
11. Add descriptive comments for traffic management purposes

**Manual Commands**:
```bash
/ip firewall layer7-protocol add name=bittorrent regexp="^(\\x13bittorrent protocol|azver\\x01\$|get /announce\\?info_hash=)" comment="Block Torrents"
/ip firewall layer7-protocol add name=youtube regexp="^.*(youtube|googlevideo)\\.com.*\$" comment="Detect YouTube"
/ip firewall filter add chain=forward layer7-protocol=bittorrent action=drop comment="Drop Torrent Traffic"
/ip firewall filter add chain=forward layer7-protocol=youtube action=accept limit=5M/5M comment="Limit YouTube"
```

---

## Example 17: Dual WAN Load Balancing

**Prompt to AI**:
```
Set up load balancing between two WAN connections. WAN1 is on ether1 with IP 
192.168.1.2/24 and gateway 192.168.1.1, WAN2 is on ether2 with IP 192.168.2.2/24 
and gateway 192.168.2.1. Configure per-connection classifier (PCC) to distribute 
traffic 50/50 between both connections, with ping check for failover, and mark 
connections and routes appropriately.
```

**What AI Will Do**:
1. Assign IP address 192.168.1.2/24 to ether1 (WAN1)
2. Assign IP address 192.168.2.2/24 to ether2 (WAN2)
3. Create route for 0.0.0.0/0 via 192.168.1.1 with routing-mark=wan1-route
4. Enable gateway ping check for route monitoring
5. Create route for 0.0.0.0/0 via 192.168.2.1 with routing-mark=wan2-route
6. Create mangle rule in prerouting chain using per-connection-classifier
7. Configure classifier to split connections 50/50 (both-addresses:2/0)
8. Mark new connections as wan1-conn
9. Create mangle rule to mark routing for wan1-conn as wan1-route
10. Set up corresponding rules for wan2-conn and wan2-route
11. Configure proper distance values for route priority

**Manual Commands**:
```bash
/ip address add address=192.168.1.2/24 interface=ether1 comment="WAN1"
/ip address add address=192.168.2.2/24 interface=ether2 comment="WAN2"
/ip route add dst-address=0.0.0.0/0 gateway=192.168.1.1 distance=1 routing-mark=wan1-route check-gateway=ping
/ip route add dst-address=0.0.0.0/0 gateway=192.168.2.1 distance=2 routing-mark=wan2-route check-gateway=ping
/ip firewall mangle add chain=prerouting in-interface=bridge connection-mark=no-mark action=mark-connection new-connection-mark=wan1-conn per-connection-classifier=both-addresses:2/0
/ip firewall mangle add chain=prerouting in-interface=bridge connection-mark=wan1-conn action=mark-routing new-routing-mark=wan1-route
```

---

## Example 18: User Management and Groups

**Prompt to AI**:
```
Create a user management structure with different access levels. Create a "monitoring" 
group with read-only access to SSH, web, and winbox. Create a "network-admin" group 
with full access except sensitive operations. Add three users: "monitor" with password 
"MonitorPass123" in monitoring group, "netadmin" with password "AdminPass456" in 
network-admin group, and "readonly" with password "ReadPass789" in read group.
```

**What AI Will Do**:
1. Create user group named "monitoring"
2. Assign policies: read, ssh, web, winbox (read-only access)
3. Add comment "Monitoring Only"
4. Create user group named "network-admin"
5. Assign policies: read, write, ssh, ftp, web, winbox, policy, test (full admin)
6. Add comment "Network Admins"
7. Create user "monitor" with password "MonitorPass123"
8. Assign to monitoring group with comment "Monitoring User"
9. Create user "netadmin" with password "AdminPass456"
10. Assign to network-admin group with comment "Network Administrator"
11. Create user "readonly" with password "ReadPass789"
12. Assign to read group with comment "Read Only User"

**Manual Commands**:
```bash
/user group add name=monitoring policy=read,ssh,web,winbox comment="Monitoring Only"
/user group add name=network-admin policy=read,write,ssh,ftp,web,winbox,policy,test comment="Network Admins"
/user add name=monitor password=MonitorPass123 group=monitoring comment="Monitoring User"
/user add name=netadmin password=AdminPass456 group=network-admin comment="Network Administrator"
/user add name=readonly password=ReadPass789 group=read comment="Read Only User"
```

---

## Example 19: SNMP Monitoring Setup

**Prompt to AI**:
```
Enable SNMP v2 for network monitoring tools. Set contact to "admin@company.com" 
and location to "Server Room", use trap version 2. Configure the default "public" 
community to allow read-only access from 192.168.1.0/24. Add a new community 
called "monitoring" with read-only access from management subnet 192.168.10.0/24, 
and create firewall rule to allow SNMP (UDP port 161) from the monitoring subnet.
```

**What AI Will Do**:
1. Enable SNMP service on the router
2. Set SNMP contact field to "admin@company.com"
3. Set SNMP location field to "Server Room"
4. Configure trap version to 2
5. Configure "public" community for address 192.168.1.0/24
6. Set read-access=yes and write-access=no for public community
7. Create new SNMP community named "monitoring"
8. Configure address 192.168.10.0/24 for monitoring community
9. Set read-only access for monitoring community
10. Create firewall filter rule in input chain
11. Match protocol UDP, destination port 161, source address 192.168.10.0/24
12. Set action to accept with comment "Allow SNMP from Monitoring"

**Manual Commands**:
```bash
/snmp set enabled=yes contact="admin@company.com" location="Server Room" trap-version=2
/snmp community set public address=192.168.1.0/24 read-access=yes write-access=no
/snmp community add name=monitoring address=192.168.10.0/24 read-access=yes write-access=no
/ip firewall filter add chain=input protocol=udp dst-port=161 src-address=192.168.10.0/24 action=accept comment="Allow SNMP from Monitoring"
```

---

## Example 20: Complete Backup and Restore Strategy

**Prompt to AI**:
```
Set up an automated backup system for my router. Create manual backup named 
"daily-backup", export configuration to "daily-config" file. Schedule automatic 
backups to run daily at 2:00 AM with date in filename. Schedule weekly cleanup 
at 3:00 AM on Sundays to delete backups older than 7 days. If USB drive is 
mounted as usb1, copy backups to USB drive in a backups folder.
```

**What AI Will Do**:
1. Execute system backup save command with name "daily-backup"
2. Execute export command to create "daily-config" file
3. Create system scheduler named "daily-backup"
4. Set start time to 02:00:00 with 1-day interval
5. Configure script to create backup with date-stamped filename
6. Add comment "Daily Backup"
7. Create system scheduler named "cleanup-old-backups"
8. Set start time to 03:00:00 with 7-day interval
9. Configure script to remove files older than 7 days (604800 seconds)
10. Use regex pattern to match backup files
11. Add comment "Weekly Cleanup"
12. Create file copy operation to USB drive (if mounted)
13. Copy all backup files to usb1/backups/ directory
14. Ensure backup rotation maintains only recent backups
15. Configure error handling for USB drive availability

**Manual Commands**:
```bash
# Create backup
/system backup save name=daily-backup

# Export configuration
/export file=daily-config

# Schedule daily backup at 2 AM
/system scheduler add name=daily-backup start-time=02:00:00 interval=1d on-event="/system backup save name=auto-backup-\$[/system clock get date]" comment="Daily Backup"

# Schedule weekly cleanup (keep last 7 backups)
/system scheduler add name=cleanup-old-backups start-time=03:00:00 interval=7d on-event="/file remove [find name~\"auto-backup\" where creation-time<([:timestamp]-604800)]" comment="Weekly Cleanup"

# Export to USB (if USB drive mounted)
/file copy [find name~"backup"] destination-path=usb1/backups/
```

---

## Query Commands Reference

Use these commands to verify your configurations:

```bash
# List all VLANs
/interface vlan print

# List all IP addresses
/ip address print

# List all IP pools
/ip pool print detail

# List DHCP servers
/ip dhcp-server print

# List DHCP networks
/ip dhcp-server network print

# List NAT rules
/ip firewall nat print

# List filter rules
/ip firewall filter print

# List routes
/ip route print

# List users
/user print

# List active connections
/ip firewall connection print

# System resources
/system resource print

# Interface statistics
/interface print stats
```


---

# Multi-Device Examples (Inventory)

The examples above target a single router. With an [inventory](../reference/devices/inventory.md)
configured, one MCP server manages a whole fleet: every tool accepts a `device`
argument naming the inventory `title` to target, and a `list_devices` tool lets
the AI discover the fleet on its own.

The prompt engineering pattern is simple: **name your devices the way you talk
about them** (`office-core`, `branch-berlin`), then refer to them by name, by
tag, or just say "all devices". The AI resolves the rest. If it ever omits or
mistypes a device, the server answers with the list of valid titles, so the AI
corrects itself on the next call.

These examples assume this inventory:

```yaml
- title: office-core
  host: 192.168.88.1
  username: admin
  tags: [office, core]
  region: NL

- title: branch-berlin
  host: 10.20.0.1
  username: admin
  tags: [branch]
  region: DE
```

---

## Example 21: Discover and Audit the Fleet

**Prompt to AI**:
```
Which MikroTik devices do you manage? For each one, show me its identity, 
RouterOS version, and which interfaces are actually running.
```

**What AI Will Do**:
1. Call `list_devices` to discover the fleet (titles, hosts, tags, regions)
2. Call `list_interfaces(device="office-core")` and filter for running interfaces
3. Call `list_interfaces(device="branch-berlin")` and do the same
4. Export the system identity from each device
5. Summarize the fleet in one table: title, host, identity, version, running interfaces

**Manual Commands**:
```bash
# on office-core
/system identity print
/system resource print
/interface print where running

# on branch-berlin
/system identity print
/system resource print
/interface print where running
```

---

## Example 22: Roll Out a VLAN Across Tagged Devices

**Prompt to AI**:
```
On every device tagged "office", create VLAN 40 on ether2 named vlan40-voip 
with IP 10.40.0.1/24. Verify each device afterwards and tell me if any of 
them failed.
```

**What AI Will Do**:
1. Call `list_devices` and select the devices whose tags include "office"
2. For each matching device (here only office-core):
   - `create_vlan_interface(device="office-core", name="vlan40-voip", vlan_id=40, interface="ether2")`
   - `add_ip_address(device="office-core", address="10.40.0.1/24", interface="vlan40-voip")`
3. Verify with `list_vlan_interfaces(device="office-core")` and `list_ip_addresses(device="office-core")`
4. Report per-device success or failure instead of assuming the writes landed

**Manual Commands**:
```bash
# on each device tagged "office"
/interface vlan add name=vlan40-voip vlan-id=40 interface=ether2
/ip address add address=10.40.0.1/24 interface=vlan40-voip
/interface vlan print
/ip address print where interface=vlan40-voip
```

---

## Example 23: Compare Configuration Between Two Devices

**Prompt to AI**:
```
Compare the firewall filter rules on office-core and branch-berlin. 
Summarize what exists on one but not the other, and flag anything on 
branch-berlin that allows traffic office-core would drop.
```

**What AI Will Do**:
1. Call `list_filter_rules(device="office-core")`
2. Call `list_filter_rules(device="branch-berlin")`
3. Diff the two rule sets by chain, action, and match criteria
4. Highlight rules present on only one device
5. Call out permissive rules on branch-berlin that contradict office-core policy
6. Present the result as a summary, not a raw dump

**Manual Commands**:
```bash
# on office-core
/ip firewall filter print detail

# on branch-berlin
/ip firewall filter print detail

# then compare the two outputs by hand
```

---

## Example 24: Risky Change on One Device, Guarded by Safe Mode

**Prompt to AI**:
```
I need to tighten the firewall on branch-berlin, but I'm remote and can't 
afford to lock myself out. Enable safe mode on it first, add a forward-chain 
drop rule for 203.0.113.0/24, show me the resulting rules, and only commit 
if the rule looks correct. office-core must not be touched.
```

**What AI Will Do**:
1. Call `enable_safe_mode(device="branch-berlin")` — safe mode is tracked per
   device, so office-core is unaffected
2. Create the rule with `create_filter_rule(device="branch-berlin", chain="forward", action="drop", dst_address="203.0.113.0/24")`
3. Verify with `list_filter_rules(device="branch-berlin")`
4. If correct: `commit_safe_mode(device="branch-berlin")` to persist
5. If wrong: `rollback_safe_mode(device="branch-berlin")` and the router reverts
   the change automatically
6. Confirm `safe_mode_status(device="office-core")` still reports inactive

**Manual Commands**:
```bash
# on branch-berlin (interactive session)
# Ctrl+X                                  <- enter safe mode
/ip firewall filter add chain=forward action=drop dst-address=203.0.113.0/24
/ip firewall filter print
# Ctrl+X                                  <- commit and leave safe mode
# (or drop the session to auto-revert)
```

---

## Example 25: Fleet-Wide DNS Record with Per-Device Verification

**Prompt to AI**:
```
Add a static DNS record printer.lan pointing to 192.168.88.50 on all devices. 
Then query each device to prove the record resolves everywhere.
```

**What AI Will Do**:
1. Call `list_devices` to enumerate the fleet
2. For each device:
   - `add_dns_static(device=..., name="printer.lan", address="192.168.88.50")`
   - `list_dns_static(device=...)` to confirm the record exists
   - `test_dns_query(device=..., hostname="printer.lan")` to prove resolution
3. Report a per-device table: created, verified, resolved

**Manual Commands**:
```bash
# on every device
/ip dns static add name=printer.lan address=192.168.88.50
/ip dns static print
:put [:resolve domain-name=printer.lan]
```
