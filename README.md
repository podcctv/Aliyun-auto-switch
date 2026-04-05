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

## 公开仓库安全配置（重点）

你提到仓库是公开的，因此：

- **不要**把 AccessKey / Telegram Token 写进代码文件。
- **不要**写在 workflow 的 `env` 块里。
- 使用 GitHub `Secrets`，并在 `run` 命令参数中引用 `${{ secrets.XXX }}`。

本项目已经按这种方式实现，敏感信息只在 Actions 运行时注入。

---

## 需要配置的 GitHub Secrets

路径：`Settings -> Secrets and variables -> Actions -> Secrets`

### Telegram

- `TG_BOT_TOKEN`
- `TG_CHAT_ID`

### 国内站 ECS

- `CN_ACCESS_KEY_ID`
- `CN_ACCESS_KEY_SECRET`
- `CN_INSTANCE_ID`
- `CN_REGION_ID`（例如 `cn-hongkong`）

### 国际站 ECS

- `INTL_ACCESS_KEY_ID`
- `INTL_ACCESS_KEY_SECRET`
- `INTL_INSTANCE_ID`
- `INTL_REGION_ID`（例如 `cn-hongkong`）

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
