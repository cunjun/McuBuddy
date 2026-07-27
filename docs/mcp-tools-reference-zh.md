# McuBuddy MCP 工具中文参考

本文档对应 `full` 配置实际注册的 116 个 MCP 工具。`core` 是默认向 AI 客户端公开的常用工具；`full-only` 只有在服务启动前设置
`MCUBUDDY_TOOL_PROFILE=full` 才会公开。工具数量代表 MCP 接口数量，不等于独立底层能力数量。

安全级别沿用 `src/McuBuddy/tool_safety.py`：

- `read-only`：只读取配置、目标状态、符号、日志或元数据。
- `execution-changing`：会暂停、恢复、复位或推进目标执行。
- `state-changing`：会修改运行态内存、寄存器、断点或监视点，通常需要确认。
- `persistent-destructive`：会安装设备包或修改 Flash 等持久状态，需要明确确认。
- `persistent`：会创建或更新主机侧项目文件，需要明确确认。
- `host-process`：会启动、停止或查询主机侧进程。
- `session-changing`：修改当前 McuBuddy 会话配置或加载的调试数据。
- `connection-changing`：打开或关闭探针、日志等连接。

参数栏只列出最常用的入口参数；完整类型和默认值以 MCP 运行时 schema 为准。

## 环境、配置与项目接入

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `doctor` | `core` | `read-only` | 无 | 检查 Python 依赖、MCP、探针、目标包和运行配置，生成只读环境体检报告。 |
| `first_contact` | `core` | `execution-changing` | `target`, `backend`, `unique_id`, `elf_path` | 执行首次板卡接入流程，连接并读取最小状态，然后给出下一步建议。 |
| `get_runtime_config` | `core` | `read-only` | 无 | 返回当前探针、日志、ELF、构建、Flash和安全限制配置。 |
| `inspect_project_memory` | `core` | `read-only` | `target_root`, `current_root`, `max_depth` | 读取目标固件项目的持久记忆；缺失时只生成待确认的初始化建议。 |
| `write_project_memory` | `core` | `persistent` | `target_root`, `content`, `confirm` | 在确认后的固件项目中创建或更新 McuBuddy 项目记忆。 |
| `list_demo_profiles` | `full-only` | `read-only` | 无 | 列出内置演示配置，便于了解可复用的目标和连接示例。 |
| `load_demo_profile` | `full-only` | `session-changing` | `profile_name` | 把指定演示配置载入当前会话。 |
| `list_tool_safety` | `core` | `read-only` | `include_hidden` | 列出当前或完整工具目录的安全等级、确认要求和执行模式。 |
| `list_validation_records` | `core` | `read-only` | 无 | 返回真实硬件验证记录，区分“代码已实现”和“板上已验证”。 |
| `list_supported_targets` | `full-only` | `read-only` | `backend` | 列出指定后端支持的目标及内置验证元数据。 |
| `match_chip_name` | `core` | `read-only` | `target`, `backend` | 把用户输入的芯片别名解析为后端接受的规范目标名。 |
| `get_target_info` | `core` | `read-only` | `target`, `backend` | 查询目标别名匹配、设备补丁和后端相关信息。 |
| `pack_diagnose` | `core` | `read-only` | `target`, `search_roots` | 查找目标所需的 CMSIS-Pack，并进行来源和校验和检查。 |
| `pack_install` | `core` | `persistent-destructive` | `target`, `destination`, `confirm` | 下载、校验并安装受信任的 CMSIS-Pack。 |
| `configure_probe` | `core` | `session-changing` | `target`, `unique_id`, `backend`, `pack_paths` | 设置探针后端、目标、探针ID、设备包和连接尝试策略。 |
| `configure_log` | `core` | `session-changing` | `uart_port`, `uart_baudrate` | 设置 UART 日志端口和波特率。 |
| `configure_elf` | `core` | `session-changing` | `elf_path` | 设置后续符号解析和 Flash 比较使用的 ELF/AXF 路径。 |
| `configure_build` | `full-only` | `session-changing` | `uv4_path`, `project_path`, `target_name` | 设置 Keil UV4、工程目标及构建和下载日志路径。 |
| `discover_keil_projects` | `core` | `read-only` | `root`, `max_depth` | 在目录中查找 Keil 工程、目标和可能的 AXF/ELF 输出。 |
| `configure_keil_project` | `core` | `session-changing` | `root`, `project_path`, `uv4_path`, `target_name` | 从工程路径或搜索根目录自动配置 Keil 构建和 ELF。 |
| `connect_with_config` | `full-only` | `connection-changing` | 无 | 使用当前会话配置连接探针及相关调试资源。 |
| `disconnect_all` | `core` | `connection-changing` | 无 | 关闭探针、日志和辅助服务等当前会话连接。 |

## 探针发现、连接与执行控制

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `list_connected_probes` | `core` | `read-only` | 无 | 枚举本机连接的 ST-Link、J-Link、CMSIS-DAP 等探针及唯一ID。 |
| `probe_connect` | `core` | `connection-changing` | `target`, `unique_id` | 使用当前后端连接指定目标和探针。 |
| `probe_disconnect` | `full-only` | `connection-changing` | 无 | 仅断开当前探针连接。 |
| `probe_halt` | `core` | `execution-changing` | 无 | 暂停目标CPU并保持当前执行位置。 |
| `probe_resume` | `core` | `execution-changing` | 无 | 从当前位置恢复目标运行。 |
| `probe_reset` | `core` | `execution-changing` | `halt` | 复位目标，可选择复位后立即暂停。 |
| `probe_step` | `full-only` | `execution-changing` | 无 | 执行一条机器指令并返回新的PC和符号。 |
| `continue_target` | `full-only` | `execution-changing` | `timeout_seconds`, `poll_interval_ms` | 恢复目标执行，并按超时和轮询设置等待。 |
| `probe_continue_until` | `full-only` | `execution-changing` | `address`, `condition_*`, `max_hits` | 运行到地址，可结合符号或寄存器条件过滤命中。 |
| `step_n_instructions` | `full-only` | `execution-changing` | `count` | 连续执行指定数量的汇编指令并记录PC轨迹。 |
| `source_step` | `full-only` | `execution-changing` | 无 | 持续执行指令直到源代码行发生变化。 |
| `step_over` | `full-only` | `execution-changing` | 无 | 执行一个源代码行，遇到函数调用时跨过调用。 |
| `step_out` | `full-only` | `execution-changing` | `timeout_seconds` | 运行到当前函数返回。 |
| `run_to_function` | `full-only` | `execution-changing` | `name`, `timeout_seconds` | 在函数入口设置临时断点并运行到该函数。 |
| `run_to_source` | `full-only` | `execution-changing` | `file`, `line`, `timeout_seconds` | 运行到指定源文件和行号。 |
| `board_smoke_test` | `full-only` | `execution-changing` | `target`, `unique_id`, `halt`, `disconnect_after` | 执行通用板卡冒烟检查，验证连接、内核和向量表等基本状态。 |

## 断点与监视点

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `set_breakpoint` | `full-only` | `state-changing` | `symbol`, `address`, `condition_*`, `confirm` | 按符号或地址设置普通或条件断点。 |
| `set_breakpoints_for_function_range` | `full-only` | `state-changing` | `start_symbol`, `end_symbol`, `confirm` | 为两个符号地址范围内的所有ELF函数批量设置断点。 |
| `clear_breakpoint` | `full-only` | `state-changing` | `symbol`, `address`, `confirm` | 按符号或地址移除一个断点。 |
| `clear_all_breakpoints` | `full-only` | `state-changing` | `confirm` | 清除当前会话中的全部断点。 |
| `list_conditional_breakpoints` | `full-only` | `read-only` | 无 | 列出当前会话登记的条件断点及条件。 |
| `probe_set_watchpoint` | `full-only` | `state-changing` | `address`, `size`, `watch_type`, `confirm` | 对内存地址设置硬件读写监视点。 |
| `probe_remove_watchpoint` | `full-only` | `state-changing` | `address`, `confirm` | 移除指定地址的硬件监视点。 |
| `probe_clear_all_watchpoints` | `full-only` | `state-changing` | `confirm` | 移除全部硬件监视点。 |

## CPU、寄存器与内存

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `read_stopped_context` | `core` | `read-only` | `include_fault_registers`, `include_logs`, `resolve_symbols` | 在已暂停状态下汇总PC、LR、SP、故障寄存器、符号和可选日志。 |
| `probe_read_registers` | `full-only` | `read-only` | 无 | 读取目标CPU通用寄存器。 |
| `probe_read_fpu_registers` | `full-only` | `read-only` | 无 | 读取支持FPU的目标浮点寄存器和状态。 |
| `probe_read_mpu_regions` | `full-only` | `state-changing` | `confirm` | 读取MPU区域配置；部分后端可能需要暂时改变调试状态。 |
| `probe_read_memory` | `full-only` | `read-only` | `address`, `size` | 从指定目标地址读取原始字节。 |
| `probe_write_memory` | `full-only` | `state-changing` | `address`, `data`, `confirm` | 向目标运行态内存写入字节。 |
| `dump_memory` | `full-only` | `read-only` | `address`, `size`, `format`, `columns` | 读取并按十六进制等格式展示一段内存。 |
| `memory_find` | `full-only` | `read-only` | `address`, `size`, `pattern`, `max_results` | 在指定内存范围搜索字节模式。 |
| `memory_snapshot` | `full-only` | `read-only` | `address`, `size`, `label` | 保存一段内存快照，供后续差异比较。 |
| `memory_diff` | `full-only` | `read-only` | `label` | 重新读取已保存区域并返回逐字节变化。 |
| `read_memory_map` | `full-only` | `read-only` | 无 | 返回Cortex-M地址空间布局和已加载ELF段映射。 |
| `read_cycle_counter` | `full-only` | `state-changing` | `confirm` | 在后端支持时启用或读取DWT周期计数器。 |

## ELF、DWARF、符号与源码

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `elf_load` | `core` | `session-changing` | `path` | 加载ELF/AXF并建立符号、段和DWARF解析上下文。 |
| `elf_addr_to_source` | `full-only` | `read-only` | `address` | 把机器地址解析为源文件和行号。 |
| `elf_list_functions` | `full-only` | `read-only` | `name_filter` | 列出ELF函数符号、地址和大小，可按名称过滤。 |
| `elf_symbol_info` | `full-only` | `read-only` | `name` | 查询单个符号的地址、大小、类型和源码位置。 |
| `read_symbol_value` | `full-only` | `read-only` | `name`, `size` | 按符号名从目标内存读取变量或链接符号值。 |
| `write_symbol_value` | `full-only` | `state-changing` | `name`, `value`, `size`, `confirm` | 按符号名修改目标内存中的整数值。 |
| `watch_symbol` | `full-only` | `read-only` | `name`, `size`, `timeout_seconds` | 轮询符号值直到发生变化或超时。 |
| `disassemble` | `full-only` | `read-only` | `address`, `count` | 反汇编指定地址开始的Thumb/Thumb-2指令。 |
| `backtrace` | `core` | `read-only` | `max_frames`, `stack_scan_words` | 通过栈扫描启发式重建Cortex-M调用链。 |
| `dwarf_backtrace` | `full-only` | `read-only` | `max_frames` | 使用DWARF CFI规则更准确地回溯调用栈。 |
| `get_locals` | `full-only` | `read-only` | 无 | 根据当前PC和DWARF信息读取局部变量及函数参数。 |
| `set_local` | `full-only` | `state-changing` | `name`, `value`, `confirm` | 修改当前栈帧中可定位的整型局部变量。 |
| `log_trace` | `full-only` | `execution-changing` | `max_steps`, `max_lines` | 单步执行并记录经过的不同源代码行。 |
| `reset_and_trace` | `full-only` | `execution-changing` | `max_steps`, `max_lines` | 复位后从复位向量开始记录源码执行轨迹。 |

## Flash、构建与固件验证

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `build_project` | `core` | `host-process` | `timeout_seconds` | 使用已配置的Keil UV4目标执行构建并解析结果。 |
| `flash_firmware` | `core` | `persistent-destructive` | `timeout_seconds`, `confirm` | 调用已配置的Keil下载流程写入固件。 |
| `erase_flash` | `full-only` | `persistent-destructive` | `start_address`, `end_address`, `chip_erase`, `confirm` | 擦除指定Flash范围或整片Flash。 |
| `program_flash` | `full-only` | `persistent-destructive` | `address`, `data`, `verify`, `confirm` | 把原始字节写入已擦除的Flash区域，可随后校验。 |
| `flash_image` | `core` | `persistent-destructive` | `path`, `address`, `erase_mode`, `verify`, `confirm` | 对二进制文件执行擦除、编程、校验和可选复位的一体化流程。 |
| `verify_flash` | `full-only` | `read-only` | `address`, `data` | 比较目标Flash内容与期望原始字节。 |
| `compare_elf_to_flash` | `core` | `read-only` | 无 | 比较ELF全部可加载段与目标实际存储内容。 |

## SVD与外设

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `svd_load` | `core` | `session-changing` | `svd_path` | 加载CMSIS-SVD，建立外设、寄存器和字段定义。 |
| `svd_list_peripherals` | `full-only` | `read-only` | 无 | 列出当前SVD中的全部外设。 |
| `svd_get_registers` | `full-only` | `read-only` | `peripheral` | 返回指定外设的寄存器布局，不访问硬件。 |
| `svd_read_peripheral` | `core` | `read-only` | `peripheral` | 读取指定外设全部寄存器并解释字段值。 |
| `svd_write_register` | `full-only` | `state-changing` | `peripheral`, `register`, `value`, `confirm` | 按SVD名称向外设寄存器写入完整32位值。 |
| `svd_write_field` | `full-only` | `state-changing` | `peripheral`, `register`, `field`, `value`, `confirm` | 通过读改写修改单个寄存器字段。 |
| `diagnose_peripheral_stuck` | `full-only` | `read-only` | `peripheral`, `symptom` | 综合SVD寄存器状态分析外设无输出或卡住的可能环节。 |

## RTOS、日志、UART、RTT与SWO

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `log_connect` | `core` | `connection-changing` | `port`, `baudrate` | 打开UART日志串口。 |
| `log_disconnect` | `full-only` | `connection-changing` | 无 | 关闭当前UART日志连接。 |
| `log_tail` | `core` | `read-only` | `line_count` | 返回日志缓冲区末尾的文本行。 |
| `uart_send` | `core` | `state-changing` | `data`, `data_format`, `confirm` | 通过UART发送十六进制字节或UTF-8文本。 |
| `uart_read_bytes` | `core` | `read-only` | `timeout_ms`, `max_bytes`, `idle_timeout_ms` | 按总超时和空闲超时读取原始UART响应字节。 |
| `uart_exchange` | `core` | `state-changing` | `data`, `data_format`, `timeout_ms`, `confirm` | 发送UART请求并在同一次调用中收集二进制响应证据。 |
| `read_rtt_log` | `core` | `read-only` | `channel`, `max_bytes`, `search_start`, `search_size` | 通过探针从RAM中查找控制块并读取SEGGER RTT日志。 |
| `read_swo_log` | `full-only` | `state-changing` | `cpu_speed_hz`, `swo_speed_hz`, `port_mask`, `confirm` | 配置并读取J-Link SWO主机缓冲区。 |
| `list_rtos_tasks` | `core` | `read-only` | `max_priorities`, `task_name_len` | 从FreeRTOS内核结构列出任务状态、优先级和栈信息。 |
| `rtos_task_context` | `core` | `read-only` | `task_name`, `task_name_len` | 读取阻塞或挂起任务保存的寄存器上下文。 |
| `rtos_switch_context` | `full-only` | `state-changing` | `task_name`, `task_name_len`, `confirm` | 把调试CPU上下文切换到指定阻塞或挂起任务。 |
| `read_stack_usage` | `full-only` | `read-only` | `canary`, `task_name_len`, `max_priorities` | 扫描FreeRTOS任务栈填充值，估算高水位和剩余空间。 |

## 证据包与高层诊断

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `collect_crash_evidence` | `core` | `execution-changing` | `auto_halt`, `include_logs`, `resolve_symbols` | 收集崩溃上下文、故障状态、栈、符号和日志，但不直接宣判根因。 |
| `collect_startup_evidence` | `core` | `execution-changing` | `reset_and_halt`, `include_logs`, `resolve_symbols` | 收集复位向量、启动上下文和日志，用于启动失败分析。 |
| `collect_peripheral_evidence` | `core` | `read-only` | `peripheral`, `include_rcc`, `include_gpio` | 汇总指定外设、RCC时钟和相关GPIO的SVD证据。 |
| `collect_rtos_evidence` | `core` | `read-only` | `task_name`, `max_priorities`, `task_name_len` | 汇总FreeRTOS任务列表和可选任务上下文。 |
| `diagnose` | `full-only` | `execution-changing` | `symptom`, `peripheral`, `suspected_stage` | 根据用户症状路由到最合适的诊断流程。 |
| `diagnose_hardfault` | `full-only` | `execution-changing` | `auto_halt`, `include_logs`, `resolve_symbols` | 采集并解释HardFault上下文、故障寄存器、栈和符号。 |
| `diagnose_startup_failure` | `full-only` | `execution-changing` | `auto_halt`, `include_logs`, `suspected_stage` | 分析复位后未进入预期启动阶段的问题。 |
| `diagnose_memory_corruption` | `full-only` | `read-only` | `stack_canary` | 扫描栈和堆区域中的破坏迹象。 |
| `diagnose_stack_overflow` | `full-only` | `read-only` | 无 | 检查Cortex-M主栈、进程栈或RTOS任务栈溢出证据。 |
| `diagnose_interrupt_issue` | `full-only` | `read-only` | 无 | 检查NVIC、向量和中断相关状态，分析中断不触发或异常触发。 |
| `diagnose_clock_issue` | `full-only` | `read-only` | 无 | 检查时钟树和相关寄存器，分析频率或时钟使能异常。 |
| `run_debug_loop` | `full-only` | `execution-changing` | `issue_description`, `build_before_debug`, `flash_before_debug` | 编排构建、可选烧录、连接、证据采集和诊断循环。 |

## GDB服务与主机进程

| 工具 | 配置 | 安全级别 | 主要参数 | 中文说明 |
|---|---|---|---|---|
| `start_gdb_server` | `full-only` | `host-process` | `port`, `allow_remote`, `target`, `unique_id` | 启动pyOCD GDB Server；远程监听需要额外确认。 |
| `stop_gdb_server` | `full-only` | `host-process` | `timeout_seconds` | 停止当前pyOCD GDB Server进程。 |
| `get_gdb_server_status` | `full-only` | `host-process` | 无 | 查询pyOCD GDB Server是否运行及其端口。 |
| `start_jlink_gdb_server` | `full-only` | `host-process` | `target`, `serial_no`, `port`, `interface`, `speed` | 启动J-Link GDB Server。 |
| `stop_jlink_gdb_server` | `full-only` | `host-process` | `timeout_seconds` | 停止当前J-Link GDB Server进程。 |
| `get_jlink_gdb_server_status` | `full-only` | `host-process` | 无 | 查询J-Link GDB Server是否运行及其端口。 |

## 数量与缩减观察

- 实际公开接口：116个。
- 默认 `core`：43个。
- `full-only`：73个。
- 最适合合并的重复形态包括执行控制、断点/监视点、内存操作、SVD读写、日志通道、GDB生命周期及专项诊断。
- 缩减工具数量时应保留原有底层函数和安全策略，把多个细粒度接口收口到约30个有明确领域边界的参数化工具；不建议做成一个无类型的万能执行工具。
