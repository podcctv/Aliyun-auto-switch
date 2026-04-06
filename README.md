# Aliyun Auto Switch

[![执行状态](../../actions/workflows/ecs-auto-switch.yml/badge.svg)](../../actions/workflows/ecs-auto-switch.yml)

用于按小时在两台阿里云 ECS 之间自动切换运行状态（一个开机、一个关机），并将执行结果推送到 Telegram。

- **国内站 ECS**（`CN_*`）
- **国际站 ECS**（`INTL_*`）

核心策略：

1. 优先根据“上次成功状态”轮转：如果当前仅一台运行，则本次切换为**另一台开机、当前运行台关机**。  
2. 若当前两台都运行或都停止（无法可靠推断上次成功状态），再回退按 `Asia/Shanghai` 时区小时奇偶策略。  
3. 小时奇偶回退策略：偶数小时国际站开机、奇数小时国内站开机。  
4. 切换时先确认目标实例可开机，再执行另一台关机。  
5. 默认安全组保持放行全部入站（TCP/UDP/ICMP 等）。  
6. 若待开机实例流量达到阈值（默认 `180GB`），触发“双保险”：启用安全组超额保护（DROP ALL 入站）并阻止/执行关机。  

---

## 1. 当前部署方式（GitHub Actions）

本仓库已配置工作流：`.github/workflows/ecs-auto-switch.yml`

触发方式：

- `schedule`: `0 * * * *`（每小时第 0 分钟执行一次）
- `workflow_dispatch`: 支持手动触发

执行流程：

1. Checkout 代码
2. 安装 Python 3.11 与依赖
3. 校验必填 secrets 是否存在
4. 运行 `python scripts/ecs_switch.py`

> 当前 job 绑定的 environment 名称是 **`env`**。如果你使用 Environment secrets，必须把所需 secrets 放在这个 environment（或修改 workflow 中的 `environment` 名称）。

---

## 2. 一次性部署步骤（推荐）

### 步骤 1：Fork / 上传仓库代码

把本仓库代码放到你的 GitHub 仓库。

### 步骤 2：配置 GitHub Secrets

路径：`Settings -> Secrets and variables -> Actions`

你可以二选一：

- **方式 A（推荐）**：全部放到 **Repository secrets**
- **方式 B**：放到 **Environment secrets**，但要保证 workflow 绑定的 environment 能读到这些 secrets（默认是 `env`）

### 步骤 3：填写必填参数（10 个）

#### Telegram（2 个）

- `TG_BOT_TOKEN`
- `TG_CHAT_ID`

#### 国内站 ECS（4 个）

- `CN_ACCESS_KEY_ID`
- `CN_ACCESS_KEY_SECRET`
- `CN_INSTANCE_ID`
- `CN_REGION_ID`

#### 国际站 ECS（4 个）

- `INTL_ACCESS_KEY_ID`
- `INTL_ACCESS_KEY_SECRET`
- `INTL_INSTANCE_ID`
- `INTL_REGION_ID`

### 步骤 4：手动触发一次验证

打开 `Actions -> ECS Auto Switch -> Run workflow` 手动运行一次，确认：

- 无 `InvalidCredentials`
- Telegram 能收到报告
- 实例启停符合当前小时策略

### 步骤 5：观察定时执行

后续将每小时自动执行一次。

---

## 3. 参数配置说明（完整）

脚本支持两种传参方式：

- 命令行参数（`--xxx`）
- 环境变量（`XXX`）

优先级：**命令行参数 > 环境变量**。

### 3.1 必填参数

| 作用 | CLI 参数 | 环境变量 | 示例 |
|---|---|---|---|
| Telegram Bot Token | `--tg-bot-token` | `TG_BOT_TOKEN` | `123456:ABC...` |
| Telegram Chat ID | `--tg-chat-id` | `TG_CHAT_ID` | `-100xxxxxxxxxx` |
| 国内站 AK | `--cn-access-key-id` | `CN_ACCESS_KEY_ID` | `LTAI...` |
| 国内站 SK | `--cn-access-key-secret` | `CN_ACCESS_KEY_SECRET` | `xxxx` |
| 国内站实例ID | `--cn-instance-id` | `CN_INSTANCE_ID` | `i-abc123` |
| 国内站地域 | `--cn-region-id` | `CN_REGION_ID` | `cn-hongkong` |
| 国际站 AK | `--intl-access-key-id` | `INTL_ACCESS_KEY_ID` | `LTAI...` |
| 国际站 SK | `--intl-access-key-secret` | `INTL_ACCESS_KEY_SECRET` | `xxxx` |
| 国际站实例ID | `--intl-instance-id` | `INTL_INSTANCE_ID` | `i-def456` |
| 国际站地域 | `--intl-region-id` | `INTL_REGION_ID` | `ap-southeast-1` |

> 兼容项：国内站/国际站 AK/SK 也可从 `ALIBABA_CLOUD_ACCESS_KEY_ID`、`ALIBABA_CLOUD_ACCESS_KEY_SECRET` 回退读取，但**不建议**与 `CN_*`、`INTL_*` 混用。

### 3.2 可选参数

| 作用 | CLI 参数 | 环境变量 | 默认值 |
|---|---|---|---|
| 开机流量阈值（GB） | `--traffic-limit-gb` | `TRAFFIC_LIMIT_GB` | `180` |
| 国内站流量文本 | `--cn-traffic-usage` | `CN_TRAFFIC_USAGE` | 空 |
| 国际站流量文本 | `--intl-traffic-usage` | `INTL_TRAFFIC_USAGE` | 空 |
| CDT 卡片名称 | `--cdt-name` | `ALIYUN_CDT_NAME` | 空 |
| CDT 进度条 | `--cdt-progress-bar` | `ALIYUN_CDT_PROGRESS_BAR` | 空 |
| CDT 百分比 | `--cdt-progress-percent` | `ALIYUN_CDT_PROGRESS_PERCENT` | 空 |
| CDT 用量 | `--cdt-usage` | `ALIYUN_CDT_USAGE` | 空 |
| CDT 地域名 | `--cdt-region-name` | `ALIYUN_CDT_REGION_NAME` | 空 |
| CDT 到期时间 | `--cdt-expires-at` | `ALIYUN_CDT_EXPIRES_AT` | 空 |
| CDT 安全组状态 | `--cdt-security-group-status` | `ALIYUN_CDT_SECURITY_GROUP_STATUS` | 空 |

---

## 4. GitHub Actions 示例配置

工作流已内置大部分配置，通常只需要填 secrets 即可运行。

如果你想改 environment 名称，例如改为 `prod`：

1. 修改 `.github/workflows/ecs-auto-switch.yml` 中：

```yaml
jobs:
  switch:
    environment: prod
```

2. 在 GitHub 中创建 `prod` environment，并把同一套 secrets 配进去。

---

## 5. 本地部署 / 本地调试

### 5.1 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5.2 用环境变量运行（推荐）

```bash
export TG_BOT_TOKEN="xxx"
export TG_CHAT_ID="xxx"

export CN_ACCESS_KEY_ID="xxx"
export CN_ACCESS_KEY_SECRET="xxx"
export CN_INSTANCE_ID="i-xxxx"
export CN_REGION_ID="cn-hongkong"

export INTL_ACCESS_KEY_ID="xxx"
export INTL_ACCESS_KEY_SECRET="xxx"
export INTL_INSTANCE_ID="i-xxxx"
export INTL_REGION_ID="ap-southeast-1"

# 可选
export TRAFFIC_LIMIT_GB="180"
export CN_TRAFFIC_USAGE="12.3GB / 180GB"
export INTL_TRAFFIC_USAGE="85.0GB / 180GB"

python scripts/ecs_switch.py
```

### 5.3 用命令行参数运行

```bash
python scripts/ecs_switch.py \
  --tg-bot-token "xxx" \
  --tg-chat-id "xxx" \
  --cn-access-key-id "xxx" \
  --cn-access-key-secret "xxx" \
  --cn-instance-id "i-xxxx" \
  --cn-region-id "cn-hongkong" \
  --intl-access-key-id "xxx" \
  --intl-access-key-secret "xxx" \
  --intl-instance-id "i-xxxx" \
  --intl-region-id "ap-southeast-1" \
  --traffic-limit-gb "180"
```

---

## 6. 常见问题排查

### 6.1 `InvalidCredentials`

通常是以下问题：

1. Secret 没填或填错（空值、拷贝时有空格/换行）
2. Environment 不匹配（workflow 用 `env`，但你把 secrets 放在别的 environment）
3. AccessKey 没有 ECS 权限
4. 把 AccessKeyId / AccessKeySecret 填反

### 6.2 工作流里 Secret 读取为空

优先检查：

- `jobs.switch.environment` 与实际 environment 名称是否一致
- 该 environment 是否允许当前分支触发
- 是否是 fork/机器人触发导致 secrets 不可用

### 6.3 流量保护触发后为什么不开机

当待开机实例流量 `>= TRAFFIC_LIMIT_GB` 时，脚本会阻止其开机，这是预期行为。
同时脚本会将该实例的安全组从“放行全部入站”切换为“DROP ALL 入站”，形成安全组 + 关机双保险。
你可以：

- 等下个计费周期回落后自动恢复
- 临时提高 `TRAFFIC_LIMIT_GB`

---

## 7. 安全建议

- 给 AK/SK 最小权限（仅允许必要的 ECS / CDT 读取与控制）
- 不要把 AK/SK 写入仓库文件
- 仅通过 GitHub Secrets 管理敏感参数
- 定期轮换 AccessKey

---

## 8. 目录结构

```text
.
├── .github/workflows/ecs-auto-switch.yml
├── scripts/ecs_switch.py
├── requirements.txt
└── README.md
```
