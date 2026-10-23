## 2024-05-24 - Batching SSH Commands over Paramiko
**Learning:** Found that sequential calls to `exec_cmd` in `MikroTikEngine` introduce significant latency because each call sets up a new paramiko channel. In a function like `get_all_devices`, multiple `print detail` commands are called sequentially, leading to compounded channel overhead.
**Action:** Always batch related RouterOS commands using `:put "---SEPARATOR---";` syntax instead of making multiple sequential `exec_cmd` calls, similar to how it is implemented in `get_system_stats`.
