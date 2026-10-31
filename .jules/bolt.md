## 2023-11-08 - Pre-compile Regexes in CLI Parsers
**Learning:** The application relies heavily on parsing MikroTik RouterOS CLI output. Pre-compiling regular expressions (using `re.compile`) at the module or class level is a critical performance pattern for these parsing hot-paths, especially when parsing large command outputs.
**Action:** Always pre-compile `re` patterns used in parsing functions.
