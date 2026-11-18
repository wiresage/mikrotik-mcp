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
