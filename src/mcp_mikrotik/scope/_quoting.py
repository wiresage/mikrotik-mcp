def ros_quoted(value: str) -> str:
    r"""Escape a value for use inside a RouterOS double-quoted string.

    Inside double quotes RouterOS treats a backslash as an escape, `"` as the end of the string and `$`
    as the start of a variable. A DNS regexp such as `.*\.example\.com$` therefore has to be sent as
    `".*\\.example\\.com\$"`; sent as it is, the router answers "expected regexp value" or
    "syntax error". The backslash is replaced first, or it would escape the escapes added after it.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
