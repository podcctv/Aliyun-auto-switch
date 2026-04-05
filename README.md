# Aliyun Auto Switch (GitHub Actions)

这个项目用于**按小时轮流**控制两台阿里云 ECS：

- 阿里云国际站 ECS
- 阿里云国内站 ECS

目标行为：

1. 每小时根据当前小时奇偶决定哪台应当开机。
2. 切换时先确保目标机器开机成功。
3. 再执行另一台关机并确认成功。
4. 把执行结果推送到 Telegram。

---

## 工作流说明

GitHub Actions 每小时触发一次（也可手动触发）：

- 偶数小时：国际站开机，国内站关机
- 奇数小时：国内站开机，国际站关机

时区使用 `Asia/Shanghai`。

---

## Secrets 配置（非常重要）

路径：`Settings -> Secrets and variables -> Actions`

### 1) 推荐：Repository secrets（最简单）

把下面 10 个 key 都配置在 **Repository secrets** 下：

#### Telegram

- `TG_BOT_TOKEN`
- `TG_CHAT_ID`

#### 国内站 ECS

- `CN_ACCESS_KEY_ID`
- `CN_ACCESS_KEY_SECRET`
- `CN_INSTANCE_ID`
- `CN_REGION_ID`

#### 国际站 ECS

- `INTL_ACCESS_KEY_ID`
- `INTL_ACCESS_KEY_SECRET`
- `INTL_INSTANCE_ID`
- `INTL_REGION_ID`

### 2) 你截图中的方式：Environment secrets

你当前是把 key 配在 **Environment secrets** 里（而且分在多个 environment）。
这会导致本工作流拿不到部分 secret，传给脚本就是空字符串，最终报：
`InvalidCredentials`。

> 原因：GitHub Actions 的一个 job 一次只能绑定 **一个** environment。

如果你坚持使用 Environment secrets，请把以上 10 个 key 放到**同一个** environment，再让 job 绑定这个 environment；否则会缺参。

当前仓库的 workflow 已默认绑定 `env` 这个 environment（见 `.github/workflows/ecs-auto-switch.yml`），
所以你在截图里使用 `env` 作为 Environment 名称是可行的。

---

## 常见报错：`InvalidCredentials`

如果报错类似：

- `Error: InvalidCredentials`
- `Please set up ... ALIBABA_CLOUD_ACCESS_KEY_ID / ALIBABA_CLOUD_ACCESS_KEY_SECRET`

优先检查：

1. 对应 secret 是否为空（尤其是配置在 Environment secrets 但 job 未绑定该 environment 的情况）。
2. `CN_*` / `INTL_*` 命名是否和 workflow 完全一致。
3. AccessKey 是否有 ECS 的操作权限。

脚本现在支持两种传参来源（任选其一）：

- 命令行参数（`--cn-access-key-id` 等）
- 环境变量（`CN_*` / `INTL_*` / `TG_*`）

并且会在缺参时直接报出明确提示。

---

## 本地运行（参数方式）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

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
  --intl-region-id "cn-hongkong"
```

## 本地运行（环境变量方式）

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
export INTL_REGION_ID="cn-hongkong"

# 可选：用于丰富 Telegram 的流量/实例展示卡片
export ALIYUN_CDT_NAME="Aliyun-CDT（47.76.68.241）"
export ALIYUN_CDT_PROGRESS_BAR="■□□□□□□□□□□□□□□□□□□□"
export ALIYUN_CDT_PROGRESS_PERCENT="0.05%"
export ALIYUN_CDT_USAGE="0.1GB / 180GB"
export ALIYUN_CDT_REGION_NAME="中国香港"
export ALIYUN_CDT_EXPIRES_AT="2099-12-31 15:59:00"
export ALIYUN_CDT_SECURITY_GROUP_STATUS="启用"

python scripts/ecs_switch.py
```
