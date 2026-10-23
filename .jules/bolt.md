## 2026-10-22 - [Performance] Pre-compiling RegEx in CLI Parsers
**Learning:** This application makes heavy use of RouterOS CLI output parsing, especially when retrieving statistics for many devices or queues (e.g., \get_all_devices\). Dynamic regex compilation inside loops processing CLI output strings (like \extract_queue_fields\) adds significant overhead and CPU cycles when dealing with hundreds or thousands of lines.
**Action:** When extracting multiple key-value pairs or fields from string outputs, prefer pre-compiling a single regular expression using \e.compile()\ outside the function and use \inditer()\ or \search()\ on it instead of repeatedly constructing regex strings using string interpolation and \e.escape()\ inside tight loops.

## 2026-10-23 - Batching SSH Commands over Paramiko
**Learning:** Found that sequential calls to \exec_cmd\ in \MikroTikEngine\ introduce significant latency because each call sets up a new paramiko channel. In a function like \get_all_devices\, multiple \print detail\ commands are called sequentially, leading to compounded channel overhead.
**Action:** Always batch related RouterOS commands using \:put " ---SEPARATOR---\;\ syntax instead of making multiple sequential \exec_cmd\ calls, similar to how it is implemented in \get_system_stats\.
