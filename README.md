# statusfooter

在 Claude Code 状态栏底部显示火山方舟 **Coding Plan** 的实时用量：

```
5h 26% ▓░░  W 62% ▓▓▓  M 31% ▓░░  ↻5h 1h19m  W 2h55m  M 26d
```

---

## 〇、产品介绍

### 这是什么

**statusfooter** 是一个跑在 Claude Code 状态栏底部的小工具，把火山方舟 **Coding Plan** 的三个限速窗口（5 小时 / 周 / 月）的当前用量、重置倒计时实时显示出来——你不用切到浏览器、不用点开火山控制台，写代码的时候顺眼就能看到「这 5 小时还能用多少」「这周还剩多少」。

### 为什么需要它

火山方舟 Coding Plan 的限速是**滚动窗口**：

- **5h**：每 5 小时会重置一次会话用量，超了就要等下个窗口
- **W**：每周一刷新，超了要等下周
- **M**：每月一刷新，超了要等下月

控制台里能看到这些数据，但每次切窗口、登录、点几下控制面板才能看，体验和「随手瞄一眼」差太远。`statusfooter` 把这条信息**塞到 Claude Code 终端最显眼的位置**，让你写着代码就知道：

- 现在用了多少 → 决定是否继续放心用 sonnet 等高级模型
- 离重置还多久 → 决定是「再等一会儿」还是「换轻量任务」
- 周/月用量 → 长期规划自己的开发节奏

### 长什么样

每秒更新一行，字段从左到右是：**5h 用量 / 周用量 / 月用量 / 三个窗口的重置倒计时**。

```
5h 44% ▓░░  W 77% ▓▓░  M 39% ▓░░  ↻5h 4h35m  W 1h11m  M 26d
```

颜色随用量自动变：**<60%** 默认色（不打扰），**60–80%** 黄色（提醒），**≥80%** 红色（警告，差不多该慢点了）。具体字段含义见 [§五 输出含义速查](#五输出含义速查)。

### 核心特性

- ✅ **三个滚动窗口同屏**：5h / 周 / 月，一行看全
- ✅ **百分比 + 进度条 + 颜色阈值**：信息密度高、扫一眼就懂
- ✅ **三个窗口的重置倒计时**：知道还要等多久而不只是"还剩多少"
- ✅ **60s 本地缓存**：状态栏每秒调用也不会打爆火山 API
- ✅ **永远 exit 0**：网络挂了/配置错了不会让 Claude Code 状态栏空白报警
- ✅ **过期缓存兜底**：API 临时不通时仍显示旧数据 + `⚠` 标记
- ✅ **零依赖**：单文件 Python 3 stdlib 脚本，没有 pip install
- ✅ **安全**：AK/SK 文件强制 `chmod 600`，仓库不含敏感信息

### 工作原理

```
Claude Code 启动状态栏
       │
       │ 每秒调用一次（设置在 settings.json 的 statusLine.command）
       ▼
~/.local/bin/statusfooter
       │
       ├─ 读 ~/.config/statusfooter/config.json（拿 AK/SK）
       │
       ├─ 看 ~/.cache/statusfooter/usage.json
       │     ├─ mtime 在 60s 内 → 直接渲染缓存（< 100ms）
       │     └─ 过期或不存在 ↓
       │
       ├─ 火山 V4 签名 → POST GetCodingPlanUsage（< 300ms）
       │     ├─ 成功 → 写缓存、渲染
       │     └─ 失败 → 用过期缓存（行尾加 ⚠）；都没有就显示 "net err"
       │
       └─ stdout 输出一行带 ANSI 颜色的字符串 + exit 0
```

简单到一眼能看明白：**60s 内的命中走缓存**，**过期/缺失才打 API**，**API 挂了用过期缓存兜底**。

### 适合谁

- 用 Claude Code 通过火山方舟调 GLM 系列模型的开发者
- 想随时知道当前 Coding Plan 用量但又不想切窗口的人
- 喜欢极简、单文件、零依赖工具的人

### 不适合谁

- 不用火山方舟的——这工具只支持 `GetCodingPlanUsage` 这一个接口
- 用 Web 版 Claude 或 IDE 插件的——`statusLine` 是 Claude Code CLI 特有的机制
- 需要图形仪表盘的——这是个状态栏，不是 Grafana

---

## 一、前置要求

| 项 | 要求 |
|---|---|
| 操作系统 | Linux / macOS（任何能跑 bash + python3 的系统） |
| Python | 3.8 及以上（`from __future__ import annotations` 兼容） |
| 火山引擎账号 | 已开通方舟 Coding Plan |
| Claude Code | 任意支持 `statusLine` 配置的版本 |

---

## 二、获取火山引擎 AK/SK

1. 打开 [火山引擎控制台](https://console.volcengine.com/)。
2. 右上角头像 → **API 访问密钥**（API Access Keys）。
3. 创建一对 AccessKey ID / Secret Access Key。
4. **强烈建议**：创建一个**子账号**，只授予 `ark` 服务的读权限，AK/SK 万一泄露损失最小。

> AK 形如 `AKLT...`，SK 是 base64-like 字符串。两者都需要。

---

## 三、安装

### 1. 克隆仓库 + 运行安装脚本

```bash
git clone <this-repo> statusfooter
cd statusfooter
./install.sh
```

安装脚本会自动：

- 把 `statusfooter` 拷到 `~/.local/bin/statusfooter`（mode 755）
- 创建 `~/.config/statusfooter/`（mode 600 配置文件）
- 创建 `~/.cache/statusfooter/`（缓存目录）
- 写一个占位 `config.json`（只在不存在时写，不会覆盖你已有的）

执行后看到：

```
Installed: /home/YOU/.local/bin/statusfooter
Created: /home/YOU/.config/statusfooter/config.json  (chmod 600)
→ Edit it and replace REPLACE_ME with your Volcengine AccessKeyId / SecretAccessKey.
```

### 2. 填入凭据

编辑 `~/.config/statusfooter/config.json`：

**火山方舟（兼容旧格式）：**

```json
{
  "ak": "AKLT...",
  "sk": "TVdK...",
  "cache_ttl": 60
}
```

**MiniMax Coding Plan（新格式）：**

```json
{
  "active": "minimax",
  "cache_ttl": 60,
  "providers": {
    "minimax": {
      "minimax_api_key": "sk-cp-..."
    }
  }
}
```

**多 Provider 共存：**

```json
{
  "active": "minimax",
  "cache_ttl": 60,
  "providers": {
    "minimax": {
      "minimax_api_key": "sk-cp-..."
    },
    "volcengine_ark": {
      "ak": "AKLT...",
      "sk": "TVdK..."
    }
  }
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `ak` | ✅（旧格式） | 火山引擎 AccessKey ID |
| `sk` | ✅（旧格式） | 火山引擎 Secret Access Key |
| `active` | ✅（新格式） | 当前激活的 provider：`volcengine_ark` 或 `minimax` |
| `minimax_api_key` | ✅（MiniMax） | MiniMax Coding Plan API Key |
| `cache_ttl` | ❌ | 缓存秒数，默认 60，可改更小（更新更快）或更大（API 调用更少） |

确认权限：

```bash
chmod 600 ~/.config/statusfooter/config.json
ls -l ~/.config/statusfooter/config.json
# -rw------- 1 you you ...
```

### 3. 命令行 smoke test

```bash
~/.local/bin/statusfooter
```

应该看到一行带颜色的输出，例如：

```
5h 44% ▓░░  W 77% ▓▓░  M 39% ▓░░  ↻5h 4h35m  W 1h11m  M 26d
```

如果看到错误信息，跳到 [§六 故障排查](#六故障排查)。

---

## 四、接入 Claude Code

### 1. 编辑 `~/.claude/settings.json`

在顶层对象里加一段 `statusLine`：

```json
{
  "statusLine": {
    "type": "command",
    "command": "/home/YOU/.local/bin/statusfooter"
  },
  ... 其他你已有的配置 ...
}
```

> 如果 `~/.local/bin` 已经在 `PATH` 里，`command` 也可以直接写 `"statusfooter"`。
> 但保险起见，写绝对路径最稳，因为 Claude Code 启动时 PATH 可能不一样。

### 2. 验证 JSON 合法

```bash
python3 -c "import json; json.load(open('$HOME/.claude/settings.json')); print('ok')"
```

### 3. 启动新会话

```bash
claude
```

终端底部应该出现状态行。每次 Claude Code 渲染状态栏（一般每秒或每次输入时）都会调用 `statusfooter`，缓存命中时 < 100ms。

---

## 五、输出含义速查

```
5h 44% ▓░░  W 22% ░░░  M 39% ▓░░  ↻5h 4h35m  W 1h11m  M 26d
└─┬─┘ │  │   │ ↑                  │ └────┬────┘
  │   │  └ 进度条（3 格）          │      │
  │   └ 剩余额度百分比              │      │
  └ 标签：5h=5小时，W=周，M=月      │      └ 倒计时段：到下次清零还剩多久
                                   └ 该百分比触发了黄色染色（22% ≤ 40%）
```

MiniMax Coding Plan 输出示例（4h + 周窗口，无月窗口）：

```
4h 68% ▓▓░  W 57% ▓░░  ↻4h 1h0m  W 4d0h
```

| 元素 | 规则 |
|---|---|
| 标签 | 火山方舟：`5h`=5小时 / `W`=周 / `M`=月；MiniMax：`4h`=4小时 / `W`=周 |
| 百分比语义 | **剩余额度**（越低越危险）—— 火山方舟和 MiniMax 一致 |
| 进度条 | `░░░` <33% / `▓░░` <67% / `▓▓░` <100% / `▓▓▓` ≥100% |
| 颜色 | >40% 默认 / 20–40% 黄 / ≤20% 红（剩余越少越危险） |
| 倒计时格式 | `<1m` / `45m` / `1h19m` / `2d3h` / `26d` / `0m`（已过期） |
| 行尾 `⚠` | 数据来自过期缓存（API 失败兜底） |
| `statusfooter: ...` | 错误降级文本，详见故障排查 |

---

## 六、故障排查

### 错误信息一览

| 输出 | 含义 | 处理 |
|---|---|---|
| `statusfooter: missing config` | 配置文件缺失或字段不全 | 跑 `./install.sh` 或检查 `~/.config/statusfooter/config.json` |
| `statusfooter: net err` | 网络失败且无可用缓存 | 检查能否访问 `open.volcengineapi.com`；首次安装常因 AK/SK 写错 |
| `statusfooter: bad resp` | API 返回了无法解析的结构 | 检查 AK/SK 是否对、火山方舟 API 是否变更 |
| `statusfooter: status=Suspended` | 套餐被暂停或过期 | 去火山控制台续费 |
| `statusfooter: err` | 未捕获异常 | 手动运行 `statusfooter > /tmp/sf.out 2>&1` 看 stderr |

### 自检命令

```bash
# 1. 直接调脚本
~/.local/bin/statusfooter

# 2. 看缓存
cat ~/.cache/statusfooter/usage.json | python3 -m json.tool

# 3. 强制刷新缓存
rm -f ~/.cache/statusfooter/usage.json
~/.local/bin/statusfooter

# 4. 看脚本本体（确认安装版本）
ls -la ~/.local/bin/statusfooter
```

### 状态栏不显示？

- 确认 `~/.claude/settings.json` 是合法 JSON：`python3 -c 'import json; json.load(open("/home/YOU/.claude/settings.json"))'`
- 确认 `command` 写的是**可执行的绝对路径**，并且这个路径在 Claude Code 启动时存在
- 完全重启 Claude Code（不是 `/clear`，是退出后重开）
- 用 `bash -x ~/.local/bin/statusfooter` 看具体哪一步失败

### 网络不通但又想看状态栏？

把 `cache_ttl` 调大（例如 86400 = 一天）。这样只要曾经成功调过一次 API，离线一天内都能看到带 ⚠ 的旧数据。

---

## 七、常见操作

### 升级到新版本

```bash
cd statusfooter
git pull
./install.sh   # 幂等：已存在的 config 不会覆盖
```

### 临时禁用

不需要卸载，注释掉 `~/.claude/settings.json` 的 `statusLine` 段即可（JSON 不支持注释，可以暂时改名 `_statusLine`）。下次 Claude Code 启动就不会调脚本了。

### 完全卸载

```bash
rm -f ~/.local/bin/statusfooter
rm -rf ~/.config/statusfooter ~/.cache/statusfooter
# 再去 ~/.claude/settings.json 删掉 statusLine 段
```

### 切换到别的子账号

直接编辑 `~/.config/statusfooter/config.json` 改 `ak` / `sk`，然后清缓存：

```bash
rm -f ~/.cache/statusfooter/usage.json
```

### 改显示频率

Claude Code 的状态栏调用频率是它自己控制的（一般每秒或每次输入）。要让数据**更新得更频繁**，把 `cache_ttl` 调小（最低建议 10 秒，再低就开始浪费 API 配额了）。

---

## 八、开发与测试

```bash
cd statusfooter
python3 -m pytest -v
```

期望：**66 passed**，跑完 < 0.1s。

完整文档：

- 设计文档：`docs/superpowers/specs/2026-06-14-statusfooter-design.md`
- 实施计划：`docs/superpowers/plans/2026-06-14-statusfooter.md`
- 开发日志：`docs/superpowers/journal/2026-06-14-statusfooter-dev-log.md`

---

## 九、安全提醒

- **AK/SK 是高权限凭据**：握有它的人能调用你账号下的任意火山服务（不止方舟）。
- 配置文件**必须** `chmod 600`，安装脚本会自动设置。
- **不要**把 `config.json` 提交到 git——本仓库的 `.gitignore` 已经处理，但你 fork 后要自己留意。
- **强烈推荐子账号**：在火山控制台创建一个只读 `ark` 权限的子账号专用于这个工具。
- 如果怀疑泄露：火山控制台 → API 密钥 → 立刻**禁用**旧 key 并创建新 key。

---

## 十、限制与已知问题

| 项 | 说明 |
|---|---|
| 支持火山方舟 + MiniMax Coding Plan | 多 provider 已落地，详见 [§十一 开发计划](#十一开发计划) |
| Python ≥ 3.10 | 用了 `dict \| None` 类型注解 |
| 缓存命中 ~75ms | Python 进程冷启占大头；状态栏体感无感知 |
| `datetime.utcnow()` Deprecation | Python 3.12+ 会抛 DeprecationWarning，stderr 被丢弃所以状态栏不受影响 |

---

## 十一、开发计划

下一阶段三件事，按预期实现顺序排列：

### 1. 显示当前模型名称 ✅ 已上线（2026-06-15）

在用量行**最前面**加一段当前正在用的模型，例如：

```
GLM-5.1  5h 32% ░░░  W 6% ░░░  M 45% ▓░░  ↻5h 1h51m  W 6d1h  M 25d
└──┬──┘
   └ 来自 Claude Code stdin 的 model.display_name
```

**实现要点：**
- Claude Code 调 `statusLine` 命令时通过 stdin 传 JSON（schema 含 `model.id` 和 `model.display_name`），脚本 `not isatty()` 时读 stdin 解析。
- `display_name` 已经是好看的形式（`GLM-5.1`、`Sonnet 4.5`），原样显示，不做二次压缩。
- 拿不到模型名时（stdin 空、非 JSON、缺字段、手动跑）静默跳过前缀，其他字段照常输出。
- 提交：`d74c9e6`（render 层支持可选前缀）+ `813f814`（main 读 stdin）。新增 8 个测试，总 53。

### 2. 支持其他 Coding Plan / Provider ✅ MiniMax 已上线

已抽象出 **provider 接口**（`fetch_*()` 函数 + `PROVIDERS` 注册表），支持：

| Provider | API | 状态 |
|---|---|---|
| 火山方舟 | `GetCodingPlanUsage` | ✅ 已支持 |
| MiniMax | `/v1/api/openplatform/coding_plan/remains` | ✅ 已支持 |
| Anthropic 官方 | usage API（待调研） | 📋 路线图 |
| 智谱 BigModel | （待调研） | 📋 路线图 |
| OpenRouter | `/api/v1/auth/key` | 📋 路线图 |
| DeepSeek 直连 | `/user/balance` | 📋 路线图 |

**配置示例（已实现）：**

```json
{
  "active": "minimax",
  "providers": {
    "volcengine_ark": { "ak": "...", "sk": "..." },
    "minimax": { "minimax_api_key": "sk-..." }
  }
}
```

**实现要点：**
- `Provider` 协议：`fetch_*(config, now) -> dict`，返回统一的 `Status` / `QuotaUsage` 结构
- `render()` 根据 `provider` 参数选择标签（5h/W/M vs 4h/W）
- 火山方舟和 MiniMax 的 `Percent` 均表示**剩余额度**（越低越危险），统一通过 `PROVIDER_REMAINING` 集合标记

### 3. 自动识别当前模型 / Coding Plan

把 1 和 2 合起来：**根据当前模型自动选对应的 provider 显示用量**。

```
sonnet-4.6  W 23% ░░░  M 41% ▓░░  ↻W 3d2h  M 18d        ← 切到 sonnet 时显示 Anthropic 余额
glm-5.1     5h 44% ▓░░  W 77% ▓▓░  M 39% ▓░░  ↻5h 4h35m  ← 切回 GLM 时显示火山余额
```

**为什么需要：** 多 provider 配置后，没人想每次切模型时手动改配置文件。状态栏要"懂上下文"。

**实现思路：**
- Claude Code 通过 stdin 传的 `model` 字段是关键信号
- 配置里给每个 provider 加 `models` 字段（白名单）：

  ```json
  { "type": "volcengine_ark", "models": ["glm-*"], "ak": "...", "sk": "..." }
  { "type": "anthropic", "models": ["claude-*"], "api_key": "..." }
  ```

- 脚本启动时 → 读模型名 → 匹配第一个 provider → 调它的 API
- 匹配不上时 fallback 到 `active` 默认 provider

### 路线图优先级

- **P0** ✅ 已上线（2026-06-15）：模型名前缀显示 — 改动最小，价值最直接
- **P1** ✅ 已上线（2026-06-24）：多 provider 抽象层 — 火山方舟 + MiniMax 双 provider 支持，含配置加载、剩余额度显示
- **P2**（下一版）：自动识别模型/provider — P0 已就绪（拿到模型名），P1 多 provider 已落地，可启动

每一步都保持**单文件 + 零依赖 + 永远 exit 0** 这三条核心约束。

