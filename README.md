# MikroTik MCP

<!-- mcp-name: io.github.wiresage/mikrotik-mcp -->

[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/jeff-nasseri-mikrotik-mcp-badge.png)](https://mseep.ai/app/jeff-nasseri-mikrotik-mcp)

[![MCP Toplist](https://mcptoplist.com/badge/io.github.wiresage%2Fmikrotik-mcp.svg)](https://mcptoplist.com/server/io.github.wiresage%2Fmikrotik-mcp)
[![Audited by AddonAudit](https://addonaudit.com/badges/audited.svg)](https://addonaudit.com/addon/io-github-wiresage-mikrotik-mcp/)
[![Website](https://img.shields.io/badge/website-mikrotik--mcp.com-007ACC?style=flat-square&logo=googlechrome&logoColor=white)](https://www.mikrotik-mcp.com/)
[![Build Status](https://img.shields.io/github/actions/workflow/status/wiresage/mikrotik-mcp/publish.yml?branch=master&label=build&style=flat-square&color=%23007ACC)](https://github.com/wiresage/mikrotik-mcp/actions/workflows/publish.yml)
[![Tests](https://img.shields.io/github/actions/workflow/status/wiresage/mikrotik-mcp/publish.yml?branch=master&label=tests&style=flat-square&color=%2300C853)](https://github.com/wiresage/mikrotik-mcp/actions/workflows/publish.yml)
[![MIT License](https://img.shields.io/github/license/wiresage/mikrotik-mcp?style=flat-square&color=%23FF6B35)](https://github.com/wiresage/mikrotik-mcp/blob/master/LICENSE)
[![Discord](https://img.shields.io/badge/Discord-Join%20us-5865F2?style=flat-square&logo=discord&logoColor=white)](https://discord.gg/kmVSpstbNU)

## Overview

MikroTik MCP provides a bridge between AI assistants and MikroTik RouterOS devices. It allows AI assistants to interact with MikroTik routers through natural language requests, executing commands like managing VLANs, configuring firewall rules, handling DNS settings, and more.

## Demo Videos

### Claude Desktop

https://github.com/user-attachments/assets/24fadcdc-c6a8-48ed-90ac-74baf8f94b59

### Inspector

https://github.com/user-attachments/assets/e0301ff2-8144-4503-83d0-48589d95027d

### Inventory
> [!NOTE]
> Since MikroTik MCP version `0.14.0`, the MikroTik MCP will allow you to manage multiple MikroTik devices within your fleet structure. The following video simply shows how to use the inventory of MikroTik devices to let LLMs talk with your MikroTik devices.

https://github.com/user-attachments/assets/185b2c39-8f55-4f26-a74c-2ac459ad38f5

## Documentation

📚 **[Full Documentation](docs/README.md)** - Complete guides, API reference, and examples

> 🌐 **Prefer to read online?** The same documentation is also published at **[www.mikrotik-mcp.com](https://www.mikrotik-mcp.com/)** ([docs](https://www.mikrotik-mcp.com/docs/)) — an optional, web-friendly way to explore the project while reviewing the repo.

### Quick Links

- **[Installation Guide](docs/getting-started/installation.md)** - Get started with MikroTik MCP
- **[API Coverage](docs/api-coverage.md)** - Implemented and planned RouterOS features
- **[Testing Guide](docs/getting-started/testing.md)** - Run integration tests
- **[Claude Desktop Integration](docs/integrations/claude-desktop.md)** - Configure for Claude Desktop
- **[MCP Inspector](docs/integrations/inspector.md)** - Interactive testing tool
- **[Contributing Guide](docs/contributing.md)** - Help improve MikroTik MCP
- **[Articles](docs/articles/README.md)** - Learning resources and tutorials
- **[Diagrams](docs/diagrams/README.md)** - Architecture and design diagrams (draw.io)

## Contributors ❤️

MikroTik MCP is built by the people below. Thank you for every commit, issue,
review and idea.

<!-- hassankhurram is listed by request: the commit carries an org email, so the
     API still reports hassan-khurram-hsol. Keep this override on regeneration.
     inistor is here for issue reports rather than merged commits, and
     lilianmoraru and Kn-ut99 for pull requests (#187, #188) that are still open,
     so the contributors API does not return them either. -->
<p>
<a href="https://github.com/jeff-nasseri" title="jeff-nasseri"><img src="https://avatars.githubusercontent.com/u/57312476?s=72" width="72" height="72" alt="jeff-nasseri" /></a>
<a href="https://github.com/goto1134" title="goto1134"><img src="https://avatars.githubusercontent.com/u/9569795?s=72" width="72" height="72" alt="goto1134" /></a>
<a href="https://github.com/vavan11" title="vavan11"><img src="https://avatars.githubusercontent.com/u/12846521?s=72" width="72" height="72" alt="vavan11" /></a>
<a href="https://github.com/shahabbahojb" title="shahabbahojb"><img src="https://avatars.githubusercontent.com/u/75182541?s=72" width="72" height="72" alt="shahabbahojb" /></a>
<a href="https://github.com/lwsinclair" title="lwsinclair"><img src="https://avatars.githubusercontent.com/u/2829939?s=72" width="72" height="72" alt="lwsinclair" /></a>
<a href="https://github.com/nieomylnieja" title="nieomylnieja"><img src="https://avatars.githubusercontent.com/u/48822818?s=72" width="72" height="72" alt="nieomylnieja" /></a>
<a href="https://github.com/hassankhurram" title="hassankhurram"><img src="https://avatars.githubusercontent.com/u/22665312?s=72" width="72" height="72" alt="hassankhurram" /></a>
<a href="https://github.com/OronF" title="OronF"><img src="https://avatars.githubusercontent.com/u/133911424?s=72" width="72" height="72" alt="OronF" /></a>
<a href="https://github.com/pdostal" title="pdostal"><img src="https://avatars.githubusercontent.com/u/1254493?s=72" width="72" height="72" alt="pdostal" /></a>
<a href="https://github.com/inistor" title="inistor"><img src="https://avatars.githubusercontent.com/u/13348711?s=72" width="72" height="72" alt="inistor" /></a>
<a href="https://github.com/paoValle" title="paoValle"><img src="https://avatars.githubusercontent.com/u/11146190?s=72" width="72" height="72" alt="paoValle" /></a>
<a href="https://github.com/lucasholman" title="lucasholman"><img src="https://avatars.githubusercontent.com/u/339287918?s=72" width="72" height="72" alt="lucasholman" /></a>
<a href="https://github.com/lilianmoraru" title="lilianmoraru"><img src="https://avatars.githubusercontent.com/u/621738?s=72" width="72" height="72" alt="lilianmoraru" /></a>
<a href="https://github.com/Kn-ut99" title="Kn-ut99"><img src="https://avatars.githubusercontent.com/u/73541663?s=72" width="72" height="72" alt="Kn-ut99" /></a>
<a href="https://github.com/vanelin" title="vanelin"><img src="https://avatars.githubusercontent.com/u/18135591?s=72" width="72" height="72" alt="vanelin" /></a>
</p>

Contributions of every kind are welcome: code, bug reports, documentation and
reviews all move the project forward. Start with the
[Contributing Guide](docs/contributing.md).

## Community

Got a question, an idea, or something you'd like to talk through? Join us on
[Discord](https://discord.gg/kmVSpstbNU). Users and contributors are both
welcome, whether you're connecting your first router or working on a PR.

## License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.
