# statusfooter 开发记录

**日期：** 2026-06-14
**目标：** 在 Claude Code 状态栏底部显示火山方舟 Coding Plan 三个滚动窗口的用量。
**结果：** ✅ 已上线，45 测试全过，已写入 `~/.claude/settings.json`。

---

## 时间线

| 阶段 | 产物 |
|---|---|
| 头脑风暴 | `docs/superpowers/specs/2026-06-14-statusfooter-design.md` |
| 写计划 | `docs/superpowers/plans/2026-06-14-statusfooter.md`（13 个任务） |
| 实现 | 13 次提交（`d369f25` → `7bc78e6`） |
| 端到端验证 | 真实凭据冷启 294ms / 缓存命中 75ms |
| 接入 | 写入 `~/.claude/settings.json` 的 `statusLine` |

---

## 关键决策

### 1. API 选型：从 `ListSeatInfos` 走到 `GetCodingPlanUsage`

最初尝试的 `ListSeatInfoUsages` / `ListSeatInfos` 返回 `Total: 0`，因为火山**个人版没有 seat 概念**。又试 `GetInferenceUsage`——返回的是按天聚合的 token 用量，不是滚动窗口。最终通过浏览器 F12 抓包定位到控制台真正用的接口：

```
POST https://open.volcengineapi.com/?Action=GetCodingPlanUsage&Version=2024-01-01
鉴权: 火山引擎 V4 签名
请求体: {}
```

返回的 `Result.QuotaUsage` 直接给三个 Level（`session` / `weekly` / `monthly`）的 `Percent` 和 `ResetTimestamp`，正好对上需求。

**经验：** 当官方 API 文档找不到合适接口时，浏览器抓包是最快的破局方式。

### 2. 形态选择：单脚本 + 文件缓存（方案 A）

考虑过：
- A. 单 Python 脚本，文件缓存（最终选择）
- B. 守护进程 + Unix socket
- C. 仅缓存最近响应、状态栏每次都打 API

方案 B 复杂度高、需要常驻进程。方案 C 在缓存未命中时延迟到 200ms。最终选 A：60s 文件缓存 + `os.replace` 原子写 + 过期缓存兜底。冷启 < 800ms，缓存命中 < 100ms，统计上 99% 的调用都命中缓存。

### 3. 显示样式：紧凑 + 颜色 + 三窗口倒计时

```
5h 26% ▓░░  W 62% ▓▓▓  M 31% ▓░░  ↻5h 1h19m  W 2h55m  M 26d
```

- 进度条故意只用 3 格——状态栏空间紧张，更细的粒度肉眼分不出。
- 颜色阈值 60% 黄、80% 红。
- 倒计时三个窗口都显示，因为用户明确说"3 个都显示"。
- `5h` 标签代替 API 内部名 `session`，对用户更直观。

### 4. 错误兜底：永远 exit 0

statusLine 命令失败会让 Claude Code 状态栏空白甚至报警。`main()` 用四层 try/except 把所有失败路径转成单行降级文本：

| 场景 | 输出 |
|---|---|
| 配置缺失 | `statusfooter: missing config` |
| 网络失败但有缓存（即便过期） | 缓存渲染 + 行尾 `⚠` |
| 网络失败且无缓存 | `statusfooter: net err` |
| 解析失败 | `statusfooter: bad resp` |
| 未知异常（最外层兜底） | `statusfooter: err` |

每个分支都 `return 0`。

---

## 架构

```
~/.claude/settings.json (statusLine.command)
        │
        ▼
~/.local/bin/statusfooter (单文件 Python，287 行)
        │
        ├─ load_config(~/.config/statusfooter/config.json)
        ├─ cached_fetch(config, ~/.cache/statusfooter/usage.json)
        │     ├─ mtime 在 60s 内 → 返回缓存
        │     ├─ 否则 → fetch_quota_usage()
        │     │         └─ sign_request() V4 签名 → POST → JSON 解析
        │     └─ 失败兜底 → 用过期缓存 + stale=True
        └─ render(result, now, stale) → 带 ANSI 的单行
```

模块组成：

| 函数 | 职责 |
|---|---|
| `progress_bar(p)` | 4 档进度条：0 → ░░░ / <34 → ▓░░ / <67 → ▓▓░ / ≥67 → ▓▓▓ |
| `format_countdown(s)` | `<1m` / `45m` / `1h19m` / `2d3h` / `26d` |
| `colorize(text, p)` | 已用语义：60% 黄、80% 红（火山方舟） |
| `colorize_remaining(text, p)` | 剩余语义：≤40% 黄、≤20% 红（MiniMax） |
| `render(result, now, stale)` | 装配最终行，按 provider 选着色函数 |
| `sign_request(...)` | 火山 V4 签名（纯函数，可测） |
| `fetch_volcengine_ark(config, now)` | 火山方舟 HTTP POST + 解析 |
| `fetch_minimax(config, now)` | MiniMax HTTP GET + 解析（剩余额度） |
| `read_cache` / `write_cache_atomic` | 缓存读写（temp + rename 原子写） |
| `cached_fetch(config, path, now)` | TTL + 过期兜底 |
| `load_config(path)` | 读 JSON、校验 ak/sk/minimax_api_key、默认 ttl=60 |
| `main()` | 顶层 try/except 兜底，永远 exit 0 |

代码组织上 9 个公开函数 + 2 个异常类，全在一个 287 行的脚本里。Python 3 标准库 only，零依赖。

---

## 开发流程：subagent-driven development

13 个任务全程用 superpowers 的 subagent-driven-development skill 执行：每个任务派发**实现 subagent**，再派发**两阶段评审**（先 spec compliance，再 code quality），有问题就回到实现 subagent 修，循环到通过为止。

**有用的几次干预：**

1. **Task 0 conftest.py：** code reviewer 指出 `importlib.machinery` 没显式导入，靠 `importlib.util` 间接载入，脆。修复后所有测试文件都加了显式 `import importlib.machinery`。

2. **Task 4 spec-vs-plan 冲突：** 实现 subagent 发现 plan 测试期望 `Percent: 25.98 → ▓░░`，但 spec 规定 `<33` 应是 `░░░`。它**错误地**把 `progress_bar` 边界改成了 `<25` 来迎合测试。我抓住后派发修复 subagent：spec 是权威的，plan 里的测试断言是 typo，把测试改回来。这是 plan / spec 冲突的标准处理姿势。

3. **Task 4 cleanup：** code reviewer 指出 DRY 机会和一个缺失的边界测试，再派发 subagent 做 `7e44f0d` 这个 refactor commit。

**模型分工：** 实现用 standard 模型，评审用 capable 模型，没出现"模型太弱"问题。

---

## 测试策略

| 测试文件 | 用例数 | 覆盖 |
|---|---|---|
| `test_render.py` | 16 | progress_bar / countdown / colorize / render 全路径 |
| `test_signature.py` | 4 | V4 签名确定性 + HTTP 客户端（monkeypatch urlopen） |
| `test_cache.py` | 14 | 缓存读写原子性 + 4 状态分支 + load_config |
| `test_main.py` | 4 | 4 个错误分支 + happy path |
| **合计** | **45** | 0.08s 跑完 |

**单元测试用纯函数 + monkeypatch**，没用真实凭据。集成测试是手动跑的（端到端 smoke）。

---

## 安全

- **AK/SK 是高权限凭据**：直接落到 `~/.config/statusfooter/config.json`，安装脚本强制 `chmod 600`。
- **`.gitignore` 不收**：配置文件不在仓库里，无论谁 push 都不会泄露。
- **建议子账号**：README 里写明推荐用最小权限（只读 `ark`）的子账号 AK/SK。

---

## 已知限制 / 未来工作

| 项 | 说明 | 优先级 |
|---|---|---|
| `datetime.utcnow()` deprecation | Python 3.12+ 会发 `DeprecationWarning`。改用 `datetime.now(datetime.UTC)` 但要适配 strftime（aware datetime 会渲染时区后缀） | 低 |
| 缓存命中 75ms（目标 30ms） | 大头是 Python 进程冷启 + 模块导入开销。要进一步压可以考虑预编译 `.pyc` 或换语言（Go / Rust）。但 Claude Code statusLine 的预算其实是 50ms-cache-budget，不是硬阈值，目前体验流畅。 | 低 |
| `cache_ttl` 类型未校验 | 配置里写成字符串会在 `cached_fetch` 比较时炸。当前 `main()` 兜底会显示 `statusfooter: err`，不影响 Claude Code | 低 |
| 支持火山方舟 + MiniMax | 多 provider 已落地（含 `PROVIDER_REMAINING` 剩余额度语义） |

---

## 文件清单

```
statusfooter/
├── statusfooter              # 287 行，可执行
├── install.sh                # 40 行，幂等
├── README.md                 # 用户文档
├── tests/
│   ├── conftest.py
│   ├── test_render.py        # 16 测试
│   ├── test_signature.py     # 4 测试
│   ├── test_cache.py         # 14 测试
│   └── test_main.py          # 4 测试
└── docs/superpowers/
    ├── specs/2026-06-14-statusfooter-design.md
    ├── plans/2026-06-14-statusfooter.md
    └── journal/2026-06-14-statusfooter-dev-log.md   ← 本文档
```

---

## 个人体会

1. **API 探索阶段最容易卡死。** 三次走错才走对，但每次走错都筛掉了一类候选——抓包反而是最快的兜底。
2. **spec / plan / 测试三者互相校对。** Task 4 的边界冲突就是因为 plan 写的测试数据和 spec 的边界规则对不上。subagent 的本能是迎合测试改实现，要靠 reviewer 把 spec 钉死。
3. **subagent-driven 的工作量不在写代码，在审查。** 13 个任务里实现 subagent 几乎都一遍过，但有 3 次需要人介入校准方向。
4. **永远 exit 0 这条规则简单粗暴但有效。** 状态栏代码挂了不能拖累主程序，宁可显示 `statusfooter: err` 也别白屏。

---

## 后续迭代：P0 — 模型名前缀（2026-06-15）

主版本上线后的第一次迭代。在状态栏最前面加上当前模型名，例如：

```
GLM-5.1  5h 32% ░░░  W 6% ░░░  M 45% ▓░░  ↻5h 1h51m  W 6d1h  M 25d
```

### 为什么做

切模型时（`/model`、不同会话用不同 model）从状态栏直接确认当前模型，避免「我以为在用 sonnet 实际是 haiku」这种困惑。

### 技术发现：Claude Code stdin 的 schema

最早不知道 Claude Code 调 statusLine 命令时会传什么。派一个 research subagent 直接反编译 Claude Code v2.1.150 的 bundle（在 `/root/.nvm/versions/node/v22.22.2/lib/node_modules/@anthropic-ai/claude-code/...`），找到 statusLine 的 input schema：JSON 经 stdin 传入，含 `model.id` 和 `model.display_name` 字段（`display_name` 形如 "GLM-5.1"、"Sonnet 4.5"，是已经压缩好的展示名）。

**经验：** 当文档没有就直接读 binary。Claude Code 是 JS bundle，反汇编不难，schema 全在源码里。

### 实施：3 个任务、TDD、两次提交

| 任务 | commit | 说明 |
|---|---|---|
| P0-T1 `render()` 接受可选 `model_name` | `d74c9e6` | 签名加 `model_name: str \| None = None`，非 None 时前缀 `f"{model_name}  "`。3 个新测试。 |
| P0-T2 `main()` 从 stdin 读取 | `813f814` | 抽 `read_stdin_model_name(stream)` 帮手，`main()` 在 `not isatty()` 时调用，stdin 空 / 非 JSON / 缺字段全部静默 fallback 到无前缀。5 个新测试。 |
| P0-T3 端到端验证 | — | 部署到 `~/.local/bin/statusfooter`，4 种 stdin 输入实测：合法 JSON、不同 display_name、空、垃圾文本，行为全对。 |

最终 53 个测试全过（45 + 3 render + 5 main），跑完 0.09s。

### 设计决策

- **格式**：`display_name` 原样显示（已经是好看的形式），不做二次压缩，不需要映射表。
- **没拿到模型名时怎么办**：静默跳过前缀，其他字段照常输出。状态栏不能因为 stdin 异常就报错。
- **`isatty()` 守卫**：手动跑 `statusfooter` 不挂载 stdin（不会卡读），Claude Code 调用时挂 stdin（会读到 JSON）。这一行是关键。
- **模型名不染色**：颜色只染百分比段，前缀保持终端默认色，避免视觉过载。

### 测试增量

```python
# tests/test_render.py 新增 3 个
test_render_with_model_prefix
test_render_model_prefix_none_unchanged   # None 与省略行为一致
test_render_model_prefix_with_stale       # 与 ⚠ 共存

# tests/test_main.py 新增 5 个
test_read_stdin_model_name_ok
test_read_stdin_model_name_invalid_json
test_read_stdin_model_name_missing_field
test_read_stdin_model_name_empty
test_main_uses_stdin_model_prefix         # 端到端：stdin → 输出前缀
```

### 个人体会（P0 篇）

5. **反编译第三方 bundle 是合法的探索手段。** Claude Code 文档没明示 statusLine stdin schema，但 binary 里全在。30 秒派一个 subagent 反编译比花半小时翻文档快。
6. **可选参数 + 静默 fallback 是状态栏代码的天然形态。** 任何「拿不到 X 就输出错误」的设计都是反模式，状态栏唯一的合约就是输出一行有用信息 + exit 0。
