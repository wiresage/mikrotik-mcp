# Security Policy

## Overview

MikroTik MCP provides programmatic access to MikroTik RouterOS devices through SSH connections. Given the sensitive nature of network infrastructure management, security is a critical concern. This document outlines our security policy and provides guidance on reporting security vulnerabilities.


## Supported Versions

MikroTik MCP is released continuously, and security fixes ship in the latest release only. Before you report a problem, please check that it still exists in the newest release and tell us which version you tested.

| Distribution | Receives security fixes |
| --- | --- |
| [`mcp-server-mikrotik`](https://pypi.org/project/mcp-server-mikrotik/) on PyPI | The latest release |
| `ghcr.io/wiresage/mikrotik-mcp` (Docker) | The `latest` tag and the newest version tag |
| Older releases | No, please upgrade |

## Reporting a Vulnerability

**Please do not report a vulnerability in a public issue, discussion or pull request.** Anything posted there is visible to everyone, including people who would exploit it, before a fix exists. Use GitHub's private vulnerability reporting instead:

1. Go to [**Report a vulnerability**](https://github.com/wiresage/mikrotik-mcp/security/advisories/new). You can also open the **Security** tab of the repository and choose **Report a vulnerability**.
2. Fill in the form and submit it. Only the maintainers, and anyone you invite to the report, can see it.

If you cannot use GitHub, open a public issue that says only that you have a security report, with no technical details, and a maintainer will arrange a private channel.

When reporting, please include:

- **Description**: A clear description of the vulnerability
- **Impact**: Potential impact if exploited
- **Reproduction Steps**: Detailed steps to reproduce the issue
- **Affected Versions**: Which versions are affected
- **Suggested Fix**: If you have suggestions for fixing the issue (optional)
- **Environment Details**: OS, Python version, and relevant configuration details

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within 7 days
- **Assessment**: Within 14 days we will tell you whether we can reproduce the issue and how severe we consider it
- **Updates**: We will update you at least every 14 days until the report is closed
- **Resolution**: We aim to release a fix within 90 days of your report. The fix and a GitHub Security Advisory that names the affected and fixed versions are published together, with a CVE requested where it applies
- **Credit**: We will credit you in the advisory (unless you prefer to remain anonymous)

If you have heard nothing after 14 days, please open a public issue that says only that a security report is waiting, with no details, so that we notice it.

### Disclosure

We follow coordinated disclosure: please keep the details private until the fixed release is out. If 90 days pass after your report without a fix or a reply from us, you are free to publish what you found.

### Scope

In scope are the `mcp-server-mikrotik` package and the `ghcr.io/wiresage/mikrotik-mcp` image built from this repository, for example:

- A tool argument that breaks out of the RouterOS command it belongs to (command injection), including in tools marked read-only
- Credentials or key material that reach logs, tool output or error messages
- A way around the protections of the HTTP transports (the IP allowlist, the `Host` and origin checks)
- Unsafe handling of SSH credentials

Out of scope are vulnerabilities in RouterOS itself (report those to MikroTik), the behavior of the AI assistant or MCP client that calls the tools, and deployments that ignore the guidance below, such as a RouterOS account with more permissions than needed. The limitations listed under [Known Security Considerations](#known-security-considerations) are documented behavior; a report that adds something new to them is still welcome.

## Security Considerations

### 1. SSH Connection Security

MikroTik MCP uses SSH to connect to RouterOS devices. Be aware of the following:

- **Host Key Verification**: The current implementation uses `AutoAddPolicy()` which automatically accepts unknown host keys. This may expose you to man-in-the-middle attacks. Consider implementing stricter host key verification for production environments.

- **Credential Storage**: SSH credentials (passwords and private keys) must be properly secured:
  - Avoid storing passwords in plain text configuration files
  - Use environment variables for sensitive credentials
  - Restrict file permissions on configuration files containing credentials
  - Consider using SSH key-based authentication instead of passwords
  - Use SSH keys with passphrases for additional security

### 2. Command Injection Risks

- The server executes SSH commands on MikroTik devices based on tool inputs
- Always validate and sanitize inputs before passing them to MikroTik commands
- Avoid constructing commands using unsanitized user input
- Be cautious when using this server in environments where untrusted users have access

### 3. Access Control

- **MCP Server Access**: Ensure that access to the MCP server is restricted to authorized users only
- **Network Segmentation**: Run the MCP server in a secure network segment
- **Authentication**: The native HTTP transports (`sse` and `streamable-http`) have **no built-in caller authentication**, and they listen on `0.0.0.0` by default. Anyone who can reach the port can use every tool with the server's RouterOS credentials. Do not expose the port to the internet or to untrusted networks: set `MIKROTIK_MCP__HOST=127.0.0.1` when only local clients need it (in a container keep it at `0.0.0.0` and publish the port as `-p 127.0.0.1:8000:8000` instead), restrict clients with `MIKROTIK_MCP__ALLOWED_IPS`, and put an authenticating reverse proxy or a VPN in front of it for any remote use. When exposing the server through MCPO or another REST gateway, always enable that gateway's authentication (API keys, OAuth, etc.)
- **Read-only Mode**: `--read-only` (`MIKROTIK_READ_ONLY=true`) only removes the modifying tools from the catalogue. It does not limit what the RouterOS account can do, so give that account only the permissions the server needs (for example the `read` policy)
- **Firewall Rules**: Implement appropriate firewall rules to restrict access to both the MCP server and MikroTik devices
- **HTTP IP Allowlist**: Set `MIKROTIK_MCP__ALLOWED_IPS` to restrict the native HTTP transports to trusted client addresses or networks; treat it as defense in depth, not authentication

### 4. Logging and Auditing

- Commands executed on MikroTik devices are logged
- Be aware that logs may contain sensitive information
- Secure log files with appropriate permissions
- Regularly review logs for suspicious activity
- Consider implementing log rotation and secure log storage

### 5. Router Configuration Changes

- This tool provides direct access to router configuration
- Changes can impact network availability and security
- Always test configuration changes in a non-production environment first
- Maintain regular backups before making significant changes
- Implement change management procedures for production environments

### 6. Backup File Security

- Backup files may contain sensitive information including:
  - Network configurations
  - Firewall rules
  - User credentials (if included)
  - VPN configurations
- Store backup files securely with encryption
- Restrict access to backup files
- Use secure channels for backup file transfers

### 7. Wireless Security

- When managing wireless configurations:
  - Use strong encryption (WPA2 or WPA3)
  - Avoid using weak pre-shared keys
  - Regularly rotate wireless passwords
  - Implement proper access control lists
  - Disable WPS if not needed

### 8. Docker Security

> ⚠️ **Environment variables are exposed by `docker inspect`.** Any value passed
> to a container as an environment variable — whether via `-e VAR=value`,
> `-e VAR` (inherited from the host shell), or `--env-file` — is stored in the
> container's configuration and shown in full by `docker inspect`. Reading a
> file into a variable (`export VAR=$(cat secret.txt)`) does **not** help: the
> resolved value still ends up in the container's environment.

When running MikroTik MCP in a container, the MikroTik password is therefore
visible to anyone who can run `docker inspect` on the host. The server logs a
warning at startup when it detects this. To reduce the exposure:

- Manage the secret through your infrastructure — Docker / Swarm secrets
  (mounted as files under `/run/secrets/`) or a secrets manager (HashiCorp
  Vault, AWS Secrets Manager) — rather than a plain environment variable
- Restrict which users can run `docker inspect` / access the Docker socket
- Don't pass credentials as literal command-line arguments (also visible in
  `docker ps` and shell history)
- Run containers with minimal privileges, keep images updated, and use pinned
  version tags

### 9. API Exposure

When exposing MikroTik MCP via REST API (using MCPO):

- Always enable API key authentication
- Use HTTPS/TLS for API endpoints
- Implement rate limiting to prevent abuse
- Monitor API usage for suspicious patterns
- Use strong, randomly generated API keys
- Rotate API keys regularly

## Security Best Practices

### For Developers

1. **Input Validation**: Always validate and sanitize inputs
2. **Error Handling**: Don't expose sensitive information in error messages
3. **Dependencies**: Keep all dependencies updated
4. **Code Review**: Review security-critical code changes carefully
5. **Testing**: Include security testing in your test suite

### For Users

1. **Principle of Least Privilege**: Create MikroTik users with minimum required permissions
2. **Network Security**:
   - Use VPNs or secure channels for remote access
   - Implement network segmentation
   - Enable firewall rules on MikroTik devices
3. **Monitoring**:
   - Monitor MikroTik logs for unauthorized access
   - Set up alerts for configuration changes
   - Review audit logs regularly
4. **Updates**:
   - Keep MikroTik MCP updated
   - Keep MikroTik RouterOS updated
   - Update Python and system packages regularly
5. **Backup Strategy**:
   - Maintain regular encrypted backups
   - Test backup restoration procedures
   - Store backups in secure, off-site locations

## Known Security Considerations

### Current Implementation Notes

1. **SSH Host Key Verification**: Uses `AutoAddPolicy()` which automatically accepts unknown host keys. This is convenient but less secure than strict host key checking.

2. **Password Logging**: Passwords are not logged, but be cautious with debug logging that might expose sensitive command parameters.

3. **Command Execution**: Direct command execution on RouterOS requires careful input validation at the application level.

4. **HTTP Transports Have No Authentication**: See [Access Control](#3-access-control). Keep them on a trusted network or behind your own authentication.

## Compliance and Standards

This project aims to align with:

- **OWASP Top 10**: Addressing common web application security risks
- **CIS Controls**: Following Center for Internet Security best practices
- **Principle of Least Privilege**: Encouraging minimal permission configurations

## Additional Resources

- [MikroTik Security Practices](https://wiki.mikrotik.com/wiki/Manual:Securing_Your_Router)
- [SSH Key-Based Authentication](https://help.mikrotik.com/docs/display/ROS/SSH)
- [OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)

## Contact

Report vulnerabilities privately, as described under [Reporting a Vulnerability](#reporting-a-vulnerability). For general security questions that do not disclose a vulnerability, please open an issue at:
https://github.com/wiresage/mikrotik-mcp/issues

---

**Remember**: Security is a shared responsibility. While we work to make MikroTik MCP as secure as possible, proper deployment, configuration, and usage are equally important.
