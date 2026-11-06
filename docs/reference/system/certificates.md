# Certificates

Tools for managing SSL/TLS certificates, CA authority templates, CRL, and ACME (Let's Encrypt) automation on RouterOS (`/certificate`).

## Inspection & Expiry Monitoring

### `list_certificates`
Lists certificates with status flags, common names, key usage, fingerprints, and validity dates.

- Parameters:
  - `name_filter` (optional): Filter certificates by name substring
  - `expired_only` (optional): Show only expired certificates (`expired=yes`)
  - `trusted_only` (optional): Show only trusted certificates (`trusted=yes`)
  - `ca_only` (optional): Show only Certificate Authorities (`authority=yes`)
  - `device` (optional): Target device

### `get_certificate`
Retrieves full details for a specific certificate including SAN, SHA-256 fingerprint, serial number, and remaining validity.

- Parameters:
  - `name`: Certificate name
  - `device` (optional): Target device

### `check_certificate_expiry`
Scans all certificates on the router and provides an immediate status report highlighting expired certificates or certificates nearing expiration.

- Parameters:
  - `device` (optional): Target device

---

## Certificate Lifecycle & CA Management

### `create_certificate`
Creates a new certificate template on the router (RSA or EC).

- Parameters:
  - `name`: Certificate name
  - `common_name`: Common Name (CN)
  - `key_size` (optional): RSA key size (`1024`, `2048`, `4096`, default: `2048`)
  - `days_valid` (optional): Validity duration in days (default: `365`)
  - `key_usage` (optional): Comma-separated key usages (e.g. `"digital-signature,key-encipherment"`)
  - `subject_alt_name` (optional): Subject Alternative Names (e.g. `"DNS:vpn.example.com,IP:10.0.0.1"`)
  - `trusted` (optional): Set trusted flag (default: `False`)
  - `device` (optional): Target device

### `sign_certificate`
Signs a certificate template, making it active for use by services (self-signed or signed by a specified CA).

- Parameters:
  - `name`: Certificate name to sign
  - `ca` (optional): Name of the signing CA certificate (omitted for self-signed)
  - `device` (optional): Target device

### `update_certificate`
Updates properties such as trusted status or name on an existing certificate.

- Parameters:
  - `name`: Certificate name
  - `trusted` (optional): Set trusted state (`True`/`False`)
  - `new_name` (optional): Rename certificate
  - `device` (optional): Target device

### `remove_certificate`
Deletes a certificate and its private key from the router.

- Parameters:
  - `name`: Certificate name to delete
  - `device` (optional): Target device

---

## ACME / Let's Encrypt Automation

### `request_acme_certificate`
Requests and provisions an automated Let's Encrypt certificate for a public domain using RouterOS v7 native ACME (`/certificate add-acme`).

- Parameters:
  - `domain`: Fully-qualified domain name (FQDN)
  - `email` (optional): Contact email address for ACME account
  - `device` (optional): Target device

---

## Import & Export

### `import_certificate`
Imports a certificate or private key from an existing file on router storage.

- Parameters:
  - `file_name`: File name on router storage
  - `passphrase` (optional): Decryption passphrase for PKCS#12 or encrypted keys (redacted from logs)
  - `device` (optional): Target device

### `export_certificate`
Exports a certificate and its private key to router storage.

- Parameters:
  - `name`: Certificate name
  - `file_name`: Target file name
  - `export_passphrase` (optional): Passphrase to protect exported file (redacted from logs)
  - `type` (optional): Export format (`"pem"` or `"pkcs12"`, default: `"pem"`)
  - `device` (optional): Target device

---

## CRL & Global Settings

### `list_crl`
Lists Certificate Revocation Lists (CRL) and their update status.

- Parameters:
  - `device` (optional): Target device

### `get_certificate_settings`
Inspects global certificate settings (trust store, CRL download/verification).

- Parameters:
  - `device` (optional): Target device

### `update_certificate_settings`
Updates global certificate settings for automatic CRL verification and trust stores.

- Parameters:
  - `crl_download` (optional): Enable or disable automatic CRL download
  - `crl_use` (optional): Enable or disable CRL checking
  - `crl_store` (optional): Storage location for CRL (`"ram"` or `"system"`)
  - `builtin_trust_store` (optional): Builtin trust store name
  - `device` (optional): Target device
