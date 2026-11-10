"""The tools, one package per feature area.

    scope/
      _shared/        helpers used by several areas (quoting, selectors); registers nothing, imports no area
      <area>/         everything for one feature area
        __init__.py   a one-line charter and `from . import a, b, c`: importing the package registers its tools
        <module>.py   tool modules: they register tools with @mcp.tool and are named after the RouterOS menu they manage
        _helper.py    a helper used by this area only (a leading underscore: it registers no tool)

A helper used by one area lives in that area's folder, a helper used by several lives in `_shared`. `app.py` imports
every area package once. To add a tool module, put it in its area and add its name to the area's `__init__.py`; to add
an area, create the package and add its name to the import list in `app.py`. `tests/unit/scope/test_layout.py` checks
these rules, so a module that is not imported by its area (and so registers nothing) fails the test suite.
"""
