import asyncio
import pytest
from unittest.mock import AsyncMock


def _run(coro):
    return asyncio.run(coro)


class FakeExecutor:
    def __init__(self, responses=None):
        self.commands = []
        self.devices = []
        self.redacted = []
        self.responses = responses or {}
        self.default_response = ""

    async def __call__(self, command, ctx, device=None, redact=None, **kwargs):
        self.commands.append(command)
        self.devices.append(device)
        if redact:
            self.redacted.extend(redact)
        for pattern in sorted(self.responses.keys(), key=len, reverse=True):
            if pattern in command:
                return self.responses[pattern]
        return self.default_response


@pytest.fixture
def ctx():
    class DummyContext:
        info = AsyncMock()
        warning = AsyncMock()
        error = AsyncMock()
    return DummyContext()


def test_list_and_get_certificates(ctx, monkeypatch):
    from mcp_mikrotik.scope import certificates

    fake = FakeExecutor({
        "/certificate print detail where name~\"my-cert\"": " 0  K  name=\"my-cert\" common-name=\"my.example.com\"\n",
        "/certificate print detail where name=\"my-cert\"": " 0  K  name=\"my-cert\" common-name=\"my.example.com\" invalid-after=2026-12-31 23:59:59\n",
        "/certificate print detail where expired=yes": "Flags: K - PRIVATE-KEY\n",
        "/certificate print detail where name=\"unknown\"": "",
        "/certificate print detail": " 0  K  name=\"my-cert\" common-name=\"my.example.com\"\n 1  KA name=\"my-ca\" common-name=\"ca.example.com\"\n",
    })
    monkeypatch.setattr(certificates, "execute_mikrotik_command", fake, raising=True)

    # 1. List certificates
    res_list = _run(certificates.mikrotik_list_certificates(ctx, device="r1"))
    assert "CERTIFICATES:" in res_list
    assert 'name="my-cert"' in res_list
    assert fake.devices[-1] == "r1"

    # With name filter
    res_filtered = _run(certificates.mikrotik_list_certificates(ctx, name_filter="my-cert"))
    assert 'where name~"my-cert"' in fake.commands[-1]
    assert 'name="my-cert"' in res_filtered

    # Empty list
    fake.default_response = "Flags: K - PRIVATE-KEY\n"
    res_empty = _run(certificates.mikrotik_list_certificates(ctx, expired_only=True))
    assert "No certificates found matching the criteria." in res_empty

    # 2. Get certificate
    res_get = _run(certificates.mikrotik_get_certificate(ctx, name="my-cert"))
    assert "CERTIFICATE DETAILS (my-cert):" in res_get
    assert 'name="my-cert"' in res_get

    # Not found
    fake.default_response = ""
    res_not_found = _run(certificates.mikrotik_get_certificate(ctx, name="unknown"))
    assert "Certificate 'unknown' not found." in res_not_found


def test_check_certificate_expiry(ctx, monkeypatch):
    from mcp_mikrotik.scope import certificates

    # Output with one expired cert and one valid cert
    sample_output = (
        " 0  KE name=\"old-vpn\" common-name=\"old.vpn\" invalid-after=2024-01-01 00:00:00\n"
        " 1  K  name=\"active-vpn\" common-name=\"active.vpn\" invalid-after=2028-01-01 00:00:00 expires-after=58w\n"
    )

    fake = FakeExecutor({
        "/certificate print detail": sample_output
    })
    monkeypatch.setattr(certificates, "execute_mikrotik_command", fake, raising=True)

    res = _run(certificates.mikrotik_check_certificate_expiry(ctx))
    assert "CERTIFICATE EXPIRY REPORT:" in res
    assert "WARNING: 1 EXPIRED certificate(s) detected:" in res
    assert "- old-vpn" in res
    assert "[EXPIRED]" in res
    assert "- active-vpn" in res
    assert "remaining: 58w" in res

    # All valid scenario
    fake.responses["/certificate print detail"] = " 0  K  name=\"active-vpn\" common-name=\"active.vpn\" invalid-after=2028-01-01 00:00:00\n"
    res_ok = _run(certificates.mikrotik_check_certificate_expiry(ctx))
    assert "OK: No expired certificates found." in res_ok

    # No certs
    fake.responses["/certificate print detail"] = ""
    res_none = _run(certificates.mikrotik_check_certificate_expiry(ctx))
    assert "No certificates found on the device." in res_none


def test_certificate_lifecycle(ctx, monkeypatch):
    from mcp_mikrotik.scope import certificates

    fake = FakeExecutor({
        "/certificate add": "",
        "/certificate sign": "progress: done\n",
        "/certificate set": "",
        "/certificate remove": "",
    })
    monkeypatch.setattr(certificates, "execute_mikrotik_command", fake, raising=True)

    # 1. Create certificate template
    res_create = _run(certificates.mikrotik_create_certificate(
        ctx,
        name="web-cert",
        common_name="router.local",
        key_size=4096,
        days_valid=730,
        key_usage="digital-signature,key-encipherment",
        subject_alt_name="DNS:router.local,IP:192.168.88.1",
        trusted=True
    ))
    assert "created successfully" in res_create
    assert '/certificate add name="web-cert"' in fake.commands[-1]
    assert 'common-name="router.local"' in fake.commands[-1]
    assert "key-size=4096" in fake.commands[-1]
    assert "days-valid=730" in fake.commands[-1]
    assert 'key-usage="digital-signature,key-encipherment"' in fake.commands[-1]
    assert "trusted=yes" in fake.commands[-1]

    # 2. Sign certificate
    res_sign = _run(certificates.mikrotik_sign_certificate(ctx, name="web-cert", ca="my-ca"))
    assert "signed successfully" in res_sign
    assert '/certificate sign [find name="web-cert"] ca="my-ca"' in fake.commands[-1]

    # 3. Update certificate
    res_upd = _run(certificates.mikrotik_update_certificate(ctx, name="web-cert", trusted=False, new_name="web-cert-v2"))
    assert "updated successfully" in res_upd
    assert '/certificate set [find name="web-cert"] trusted=no name="web-cert-v2"' in fake.commands[-1]

    assert "No updates specified." in _run(certificates.mikrotik_update_certificate(ctx, name="web-cert"))

    # 4. Remove certificate
    res_rem = _run(certificates.mikrotik_remove_certificate(ctx, name="web-cert"))
    assert "removed successfully" in res_rem
    assert '/certificate remove [find name="web-cert"]' in fake.commands[-1]


def test_acme_and_file_transfer(ctx, monkeypatch):
    from mcp_mikrotik.scope import certificates

    fake = FakeExecutor({
        "/certificate add-acme": "progress: challenge initiated\n",
        "/certificate import": "imported: 1\n",
        "/certificate export-certificate": "",
    })
    monkeypatch.setattr(certificates, "execute_mikrotik_command", fake, raising=True)

    # 1. ACME request
    res_acme = _run(certificates.mikrotik_request_acme_certificate(ctx, domain="vpn.example.com", email="admin@example.com"))
    assert "initiated successfully" in res_acme
    assert '/certificate add-acme domain="vpn.example.com" email="admin@example.com"' in fake.commands[-1]

    # 2. Import certificate
    res_imp = _run(certificates.mikrotik_import_certificate(ctx, file_name="cert.p12", passphrase="pass123"))
    assert "imported successfully" in res_imp
    assert '/certificate import file-name="cert.p12" passphrase="pass123"' in fake.commands[-1]
    assert "pass123" in fake.redacted

    # 3. Export certificate
    res_exp = _run(certificates.mikrotik_export_certificate(
        ctx,
        name="web-cert",
        file_name="web-export",
        export_passphrase="exportpass",
        type="pkcs12"
    ))
    assert "exported successfully" in res_exp
    assert '/certificate export-certificate [find name="web-cert"] file-name="web-export" type=pkcs12 export-passphrase="exportpass"' in fake.commands[-1]
    assert "exportpass" in fake.redacted


def test_crl_and_settings(ctx, monkeypatch):
    from mcp_mikrotik.scope import certificates

    fake = FakeExecutor({
        "/certificate crl print detail": " 0   url=\"http://crl.example.com/ca.crl\"\n",
        "/certificate settings print": "builtin-trust-store: default\ncrl-use: yes\n",
        "/certificate settings set": "",
    })
    monkeypatch.setattr(certificates, "execute_mikrotik_command", fake, raising=True)

    # 1. List CRL
    res_crl = _run(certificates.mikrotik_list_crl(ctx, device="r1"))
    assert "CERTIFICATE REVOCATION LISTS (CRL):" in res_crl
    assert "crl.example.com" in res_crl
    assert fake.devices[-1] == "r1"

    # 2. Get settings
    res_sett = _run(certificates.mikrotik_get_certificate_settings(ctx))
    assert "CERTIFICATE SETTINGS:" in res_sett
    assert "builtin-trust-store: default" in res_sett

    # 3. Update settings
    res_upd = _run(certificates.mikrotik_update_certificate_settings(
        ctx,
        crl_download=True,
        crl_use=True,
        crl_store="ram",
        builtin_trust_store="custom"
    ))
    assert "updated successfully" in res_upd
    assert '/certificate settings set crl-download=yes crl-use=yes crl-store=ram builtin-trust-store="custom"' in fake.commands[-1]

    assert "No updates specified." in _run(certificates.mikrotik_update_certificate_settings(ctx))


def test_invalid_names_and_inputs(ctx):
    from mcp_mikrotik.scope import certificates

    assert "Invalid certificate name" in _run(certificates.mikrotik_get_certificate(ctx, name="bad;cert"))
    assert "Invalid certificate name" in _run(certificates.mikrotik_create_certificate(ctx, name="bad cert", common_name="c"))
    assert "Invalid domain name" in _run(certificates.mikrotik_request_acme_certificate(ctx, domain="bad domain;!"))
