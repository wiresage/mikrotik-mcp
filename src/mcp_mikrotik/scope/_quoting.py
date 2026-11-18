import re


def ros_quoted(value: str) -> str:
    r"""Escape a value for use inside a RouterOS double-quoted string.

    Inside double quotes RouterOS treats a backslash as an escape, `"` as the end of the string and `$`
    as the start of a variable. A DNS regexp such as `.*\.example\.com$` therefore has to be sent as
    `".*\\.example\\.com\$"`; sent as it is, the router answers "expected regexp value" or
    "syntax error". A comment such as `say "hi"` ends the command early ("expected end of command"), `a\b`
    is stored with a backspace in it, and `cost $5` loses the `$5`.

    Anything that is not printable ASCII goes out as `\XX` byte escapes (the UTF-8 bytes of the character).
    RouterOS reads the command byte by byte and turns UTF-8 bytes that arrive as they are into spaces, so
    `é` would be stored as a blank; `\C3\A9` is stored, and printed back, as `é`. A newline or a tab
    cannot sit inside a command line at all and is sent the same way.

    Each character is handled once, so the escapes added here are never escaped again.
    """
    out = []
    for char in value:
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char == "$":
            out.append("\\$")
        elif " " <= char <= "~":
            out.append(char)
        else:
            out.extend(f"\\{byte:02X}" for byte in char.encode("utf-8", errors="replace"))
    return "".join(out)


# Characters that cannot end a token, start a command or open a substitution: letters,
# digits and the punctuation RouterOS values are actually made of — addresses and
# prefixes (`10.0.0.0/24`), ranges (`10.0.0.1-10.0.0.9`), durations (`1d`), internal ids
# (`*3`), and the comma-separated lists of `tcp-flags`, `ranges` or `headers`. Absent from
# it on purpose: whitespace, `;`, `"`, `\`, `$`, `[`, `]`, `{`, `}`, `(`, `)`, `'` and `=`.
_BARE = re.compile(r"[A-Za-z0-9._:/,!*+-]+")


def ros_value(value: str) -> str:
    r"""A free-text value ready to drop into a command, quoted only when it has to be.

    `ros_quoted` escapes what is already inside quotes. Most interpolations are not: they reach the
    command bare, as in `/interface vlan add name={name}`, so a value carrying a space, a `;` or a
    `"` is read as further arguments or further commands.

    A value made only of safe characters is returned as it is, so a command that was already correct
    keeps its exact shape. That matters beyond the diff: RouterOS fixed "quoted input issues for
    multi-argument properties" only in 7.24beta2, so quoting a list such as `tcp-flags=syn,!ack`
    unconditionally would break it on earlier releases. Anything else is escaped and wrapped, and
    the quotes are added here rather than written into the f-string, so the surrounding literal may
    be delimited by either quote.
    """
    if value and _BARE.fullmatch(value):
        return value
    return '"' + ros_quoted(value) + '"'
