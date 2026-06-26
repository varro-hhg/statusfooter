# statusfooter 设计文档

## 一句话目标

在 Claude Code 状态栏底部显示当前 Coding Plan 的滚动窗口百分比、进度条、颜色阈值与重置倒计时。支持火山方舟（5h/W/M，已用百分比）和 MiniMax（4h/W，剩余额度）两种 provider；MiniMax 通过 `PROVIDER_REMAINING` 标记走"低=危险"的剩余语义。

## 背景与约束

- 用户使用 Claude Code 通过火山引擎方舟（`ark.cn-beijing.volces.com/api/coding`）调用 GLM-5.1。
- 火山方舟个人版 Coding Plan 有三个限速窗口，控制台展示用量。
- Claude Code 自带 `statusLine` 配置——执行命令、把 stdout 渲染在底部。需求与该机制天然契合。

**已验证可用的数据源**：

```
POST https://open.volcengineapi.com/?Action=GetCodingPlanUsage&Version=2024-01-01
鉴权: 火山引擎 V4 签名（AK/SK）
请求体: {}
```

返回：

```json
{
  "Result": {
    "Status": "Running",
    "UpdateTimestamp": 1781442276,
    "QuotaUsage": [
      {"Level": "session", "Percent": 25.98, "ResetTimestamp": 1781447046},
      {"Level": "weekly",  "Percent": 61.55, "ResetTimestamp": 1781452800},
      {"Level": "monthly", "Percent": 30.77, "ResetTimestamp": 1783699199}
    ]
  }
}
```

字段语义：
- `Level: session` = 5 小时滚动窗口（UI 里显示为 `5h`）
- `Percent` = 已用百分比（火山方舟；MiniMax 是剩余额度，由 `PROVIDER_REMAINING` 标记）
- `ResetTimestamp` = 该窗口下次清零的 Unix 秒

约束：
- 状态栏命令应在 < 50ms 内返回（缓存命中时）。第一次 / 缓存过期时 API 调用约 200ms，可接受。
- 不能阻断 Claude Code：脚本任何异常都必须 `exit 0`、stdout 输出降级文本。
- AK/SK 是高权限凭据，配置文件需 `chmod 600`，且不进 git。

## 架构

```
┌─────────────────────────┐
│ Claude Code statusLine  │  settings.json: { "statusLine": { "command": "statusfooter" } }
└────────────┬────────────┘
             │ exec
             ▼
┌──────────────────────────────────────────┐
│  statusfooter (Python 单脚本)             │
│   ┌──────────────────────────────────┐   │
│   │ 读 ~/.cache/statusfooter/usage.json │   │
│   │ mtime ≤ TTL(60s) 用缓存；否则:      │   │
│   │   读 config → 签名 → POST → 写缓存   │   │
│   └──────────────────────────────────┘   │
│   ┌──────────────────────────────────┐   │
│   │ render(quota, now) → ANSI 字符串    │   │
│   └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
             │ stdout
             ▼ Claude Code 渲染到底部
```

## 组件

### 1. `statusfooter` 脚本

位置：`~/.local/bin/statusfooter`，单文件 Python，纯标准库（`hmac`/`hashlib`/`json`/`urllib`/`datetime`/`pathlib`/`os`/`sys`/`tempfile`）。

模块边界（同一文件内的函数划分）：

| 函数 | 职责 | 依赖 |
|---|---|---|
| `load_config()` | 读取 `~/.config/statusfooter/config.json`，返回 `{"ak", "sk", "cache_ttl"}`。文件不存在时抛特定异常 | 无 |
| `fetch_quota_usage(ak, sk)` | 火山 V4 签名，POST `GetCodingPlanUsage`，返回 `Result` dict | `load_config` |
| `cached_fetch(config)` | 缓存层：读 `~/.cache/statusfooter/usage.json`，过期/不存在时调 `fetch_quota_usage`，原子写回 | `fetch_quota_usage` |
| `render(quota, now)` | 把 `Result` dict 渲染为带 ANSI 颜色的字符串 | 纯函数，无副作用 |
| `main()` | 顶层入口：try/except 包住所有逻辑，保证 `exit 0` | 全部 |

### 2. 配置文件

`~/.config/statusfooter/config.json`：

```json
{
  "ak": "AKLT...",
  "sk": "TVdK...",
  "cache_ttl": 60
}
```

- `cache_ttl` 可选，默认 60。
- 安装脚本要 `chmod 600`。
- `.gitignore` 不收。

### 3. 缓存文件

`~/.cache/statusfooter/usage.json`：

```json
{
  "fetched_at": 1781442276,
  "result": { ... 原样保存 API 的 Result ... }
}
```

- 用文件 **mtime** 判过期（`time.time() - mtime < cache_ttl` → 命中），不依赖 `fetched_at` 字段判过期（mtime 更准确）。`fetched_at` 仅用于 UI 显示「数据何时拉取」（本期不显示，留作扩展）。
- 写入用「temp file + os.rename」原子写，避免被并发读到半截内容。

## 数据流

```
statusLine 触发
    │
    ▼
main()
    │
    ▼
load_config()  ──失败──→ print("statusfooter: missing config"); exit 0
    │ ok
    ▼
cached_fetch()
    │
    ├── 缓存命中(mtime ≤ TTL) → 返回缓存
    │
    └── 缓存未命中 → fetch_quota_usage()
              │
              ├── 成功 → 原子写缓存 → 返回新数据
              │
              └── 失败:
                    ├── 有过期缓存 → 用过期缓存，render 时加 ⚠
                    └── 无缓存 → print("statusfooter: net err"); exit 0
    │
    ▼
render(quota, now=time.time())
    │
    ▼
print 到 stdout, exit 0
```

## 渲染规则

### 输出格式（紧凑 + 颜色 + 三窗口倒计时）

```
5h 26% ▓░░  W 62% ▓▓▓  M 31% ▓░░  ↻5h 1h19m W 2h55m M 26d
```

### 字段细则

**百分比**：四舍五入到整数（`round(percent)`）。

**进度条**：3 格定长，规则：
- `p == 0`：`░░░`（完全空，专留给 0）
- `0 < p < 34`：`▓░░`
- `34 ≤ p < 67`：`▓▓░`
- `p ≥ 67`：`▓▓▓`

> 注：3 格刻意粗糙——状态栏空间紧张，更细的粒度看不出差异。**0 单独处理**（仅当 p=0 显示空进度条），任何非零进度都至少有一格。

**颜色阈值**（每个窗口独立判定，只染色「百分比 + 进度条」段）：

| Percent | ANSI |
|---|---|
| `< 60` | 默认无色 |
| `60 ≤ p < 80` | 黄 `\033[33m` |
| `≥ 80` | 红 `\033[31m` |

每段染色后必须 `\033[0m` 复位。标签（`5h` `W` `M`）始终默认色。

**倒计时格式化**（输入：未来 Unix 秒；输出：紧凑字符串）：

| 剩余时间 | 格式 |
|---|---|
| `< 1 分钟` | `<1m` |
| `< 1 小时` | `45m` |
| `< 24 小时` | `1h19m`（小时 + 分钟，分钟向下取整） |
| `< 7 天` | `2d3h`（天 + 小时） |
| `≥ 7 天` | `26d`（仅天） |
| 已过期（应当极少见） | `0m` |

**倒计时段拼接**：`↻5h 1h19m  W 2h55m  M 26d`（标签 `5h`/`W`/`M` 与对应 Level 一一对应；多空格做视觉分隔）。倒计时段默认色，不参与百分比阈值染色。

### Level → 标签映射

| API `Level` | UI 标签 |
|---|---|
| `session` | `5h` |
| `weekly`  | `W`  |
| `monthly` | `M`  |

未知 `Level` 直接跳过（不报错，向前兼容）。

**输出顺序**：始终按 `5h → W → M` 排列（不依赖 API 返回顺序）。倒计时段同序。

### Status 异常处理

- `Status == "Running"` → 正常渲染。
- 其他值（如 `Suspended`、`Expired`）→ 输出 `statusfooter: status=<X>`，不渲染百分比。

### 降级显示

- 用过期缓存时，整行末尾加空格 + `⚠`。
- 无任何数据时，仅输出错误标签（如 `statusfooter: net err`），保持单行。

## 错误处理

| 场景 | 行为 | exit code |
|---|---|---|
| 配置文件不存在 / 字段缺失 | stdout: `statusfooter: missing config` | 0 |
| 网络/HTTP 失败，**有**缓存（即便已过期） | 用过期缓存渲染，行尾加 `⚠` | 0 |
| 网络/HTTP 失败，**无**缓存 | stdout: `statusfooter: net err` | 0 |
| API 返回非 2xx | 同上：用过期缓存或 `statusfooter: api err` | 0 |
| 响应缺少 `Result.QuotaUsage` | stdout: `statusfooter: bad resp` | 0 |
| 任何未捕获异常 | `try/except Exception` 兜底，stdout: `statusfooter: err` | 0 |

`stderr` 始终静默丢弃。**永远 `exit 0`**——statusLine 失败会让 Claude Code 状态栏空白甚至报警，必须避免。

## 安装

提供 `install.sh`：

```bash
#!/usr/bin/env bash
set -euo pipefail

install -m755 statusfooter "$HOME/.local/bin/statusfooter"

mkdir -p "$HOME/.config/statusfooter" "$HOME/.cache/statusfooter"

if [ ! -f "$HOME/.config/statusfooter/config.json" ]; then
  cat > "$HOME/.config/statusfooter/config.json" <<EOF
{
  "ak": "REPLACE_ME",
  "sk": "REPLACE_ME",
  "cache_ttl": 60
}
EOF
  chmod 600 "$HOME/.config/statusfooter/config.json"
  echo "请编辑 ~/.config/statusfooter/config.json 填入 AK/SK"
fi

echo "完成。在 ~/.claude/settings.json 中加入:"
echo '  "statusLine": { "type": "command", "command": "statusfooter" }'
```

**接入 Claude Code** —— 用户手动改 `~/.claude/settings.json`：

```json
{
  "statusLine": {
    "type": "command",
    "command": "statusfooter"
  }
}
```

## 测试策略

### 单元测试（pure 函数，无外部依赖）

`tests/test_render.py`：
- `render()` 给定固定 `quota` + `now`，断言输出字符串完全匹配（含 ANSI）。
- 覆盖：百分比 0/33/66/80/100、不同 Level 顺序、Status 异常、过期缓存的 `⚠` 标记。
- 倒计时格式化：分别测 30s / 45m / 1h19m / 2d3h / 26d / 已过期。
- 颜色阈值：59 / 60 / 79 / 80 / 100 五个边界。

`tests/test_signature.py`：
- 火山 V4 签名是确定性的（给固定 AK/SK/时间/body）→ 断言 `Authorization` 头匹配预期值。

### 集成测试（需真实凭据，标记为可选）

`tests/integration_test.py`（默认跳过，环境变量启用）：
- 用真实 AK/SK 调一次 `fetch_quota_usage()`，断言返回 dict 含三个 Level。

### 手动验收

- 首次冷启：`time statusfooter` < 800ms。
- 缓存命中：`time statusfooter`（再次）< 30ms。
- 删除配置：输出 `statusfooter: missing config`、退出码 0。
- 断网：输出末尾带 `⚠`、退出码 0。
- 装好后在 Claude Code 里启动一次会话，肉眼确认底部状态栏渲染正确。

## 项目结构

```
statusfooter/
├── statusfooter           # 单文件可执行脚本（带 #!/usr/bin/env python3）
├── install.sh             # 安装脚本
├── tests/
│   ├── test_render.py
│   └── test_signature.py
├── README.md              # 用法
├── .gitignore             # 忽略 ~/.config/statusfooter/* 之类（虽然不在 repo 里，但提醒）
└── docs/
    └── superpowers/specs/
        └── 2026-06-14-statusfooter-design.md
```

## 不做的事（YAGNI）

- 不做多账号/多模型供应商支持——只支持火山方舟 Coding Plan。
- 不做 GUI / TUI 配置工具——TOML/JSON 手动改即可。
- 不做后台守护进程——单脚本 + 缓存够用。
- 不显示 token 数 / 请求次数——百分比已含信息。
- 不做日志文件——`stderr` 丢弃；调试时用户可手动 `statusfooter > /tmp/sf.out 2>&1`。
- 不做自动补 AK/SK 的 OAuth 流程——AK/SK 一次性配置。

## 风险与权衡

| 风险 | 影响 | 缓解 |
|---|---|---|
| 火山 OpenAPI `GetCodingPlanUsage` 改名/下线 | 状态栏失效 | 错误降级为 `api err`，不阻断 Claude Code |
| AK/SK 泄露 | 攻击者可用账号下任意火山服务 | 配置文件 `chmod 600`；README 提醒「最小权限子账号」 |
| 缓存被并发写损坏 | 一次渲染失败 | 原子写（temp + rename）+ 解析失败时回退 fetch |
| API 稳定性 200ms 偏慢 | 缓存未命中时渲染卡 200ms | TTL 60s 已大幅降低命中频率；无更优解 |
