import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from alibabacloud_ecs20140526 import models as ecs_models
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_openapi.exceptions import ClientException


@dataclass
class InstanceConfig:
    name: str
    access_key_id: str
    access_key_secret: str
    region_id: str
    instance_id: str


@dataclass
class RuntimeConfig:
    tg_bot_token: str
    tg_chat_id: str
    cn: InstanceConfig
    intl: InstanceConfig
    traffic_card: "TrafficCardConfig"
    cn_traffic_usage: str
    intl_traffic_usage: str
    traffic_limit_gb: float


@dataclass
class TrafficCardConfig:
    cdt_name: str
    progress_bar: str
    progress_percent: str
    usage: str
    region_name: str
    expires_at: str
    security_group_status: str


@dataclass
class InstanceSnapshot:
    instance_name: str
    public_ip: str
    expired_time: str


def normalize_value(raw: str | None) -> str:
    if raw is None:
        return ""
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def pick_value(cli_value: str | None, *env_keys: str) -> str:
    cli_normalized = normalize_value(cli_value)
    if cli_normalized:
        return cli_normalized

    for key in env_keys:
        value = normalize_value(os.getenv(key))
        if value:
            return value
    return ""


def ensure_required(value: str, field_name: str, env_names: list[str]) -> str:
    if value:
        return value
    env_hint = " / ".join(env_names)
    raise ValueError(
        f"缺少必填参数: {field_name}。请通过命令行参数或环境变量设置（{env_hint}）。"
        "\n如果在 GitHub Actions 使用 Environment secrets，请确认 job 已绑定对应 environment，"
        "否则 secrets 会是空字符串。"
    )


def parse_args() -> RuntimeConfig:
    parser = argparse.ArgumentParser(description="Aliyun ECS 按小时交替开关机")

    parser.add_argument("--tg-bot-token")
    parser.add_argument("--tg-chat-id")

    parser.add_argument("--cn-access-key-id")
    parser.add_argument("--cn-access-key-secret")
    parser.add_argument("--cn-instance-id")
    parser.add_argument("--cn-region-id")

    parser.add_argument("--intl-access-key-id")
    parser.add_argument("--intl-access-key-secret")
    parser.add_argument("--intl-instance-id")
    parser.add_argument("--intl-region-id")

    parser.add_argument("--cdt-name")
    parser.add_argument("--cdt-progress-bar")
    parser.add_argument("--cdt-progress-percent")
    parser.add_argument("--cdt-usage")
    parser.add_argument("--cdt-region-name")
    parser.add_argument("--cdt-expires-at")
    parser.add_argument("--cdt-security-group-status")
    parser.add_argument("--cn-traffic-usage")
    parser.add_argument("--intl-traffic-usage")
    parser.add_argument("--traffic-limit-gb")

    args = parser.parse_args()

    tg_bot_token = ensure_required(pick_value(args.tg_bot_token, "TG_BOT_TOKEN"), "--tg-bot-token", ["TG_BOT_TOKEN"])
    tg_chat_id = ensure_required(pick_value(args.tg_chat_id, "TG_CHAT_ID"), "--tg-chat-id", ["TG_CHAT_ID"])

    cn = InstanceConfig(
        name="国内站",
        access_key_id=ensure_required(
            pick_value(args.cn_access_key_id, "CN_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_ID"),
            "--cn-access-key-id",
            ["CN_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_ID"],
        ),
        access_key_secret=ensure_required(
            pick_value(args.cn_access_key_secret, "CN_ACCESS_KEY_SECRET", "ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            "--cn-access-key-secret",
            ["CN_ACCESS_KEY_SECRET", "ALIBABA_CLOUD_ACCESS_KEY_SECRET"],
        ),
        region_id=ensure_required(pick_value(args.cn_region_id, "CN_REGION_ID"), "--cn-region-id", ["CN_REGION_ID"]),
        instance_id=ensure_required(pick_value(args.cn_instance_id, "CN_INSTANCE_ID"), "--cn-instance-id", ["CN_INSTANCE_ID"]),
    )
    intl = InstanceConfig(
        name="国际站",
        access_key_id=ensure_required(
            pick_value(args.intl_access_key_id, "INTL_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_ID"),
            "--intl-access-key-id",
            ["INTL_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_ID"],
        ),
        access_key_secret=ensure_required(
            pick_value(args.intl_access_key_secret, "INTL_ACCESS_KEY_SECRET", "ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            "--intl-access-key-secret",
            ["INTL_ACCESS_KEY_SECRET", "ALIBABA_CLOUD_ACCESS_KEY_SECRET"],
        ),
        region_id=ensure_required(
            pick_value(args.intl_region_id, "INTL_REGION_ID"),
            "--intl-region-id",
            ["INTL_REGION_ID"],
        ),
        instance_id=ensure_required(
            pick_value(args.intl_instance_id, "INTL_INSTANCE_ID"),
            "--intl-instance-id",
            ["INTL_INSTANCE_ID"],
        ),
    )

    return RuntimeConfig(
        tg_bot_token=tg_bot_token,
        tg_chat_id=tg_chat_id,
        cn=cn,
        intl=intl,
        traffic_card=TrafficCardConfig(
            cdt_name=pick_value(args.cdt_name, "ALIYUN_CDT_NAME"),
            progress_bar=pick_value(args.cdt_progress_bar, "ALIYUN_CDT_PROGRESS_BAR"),
            progress_percent=pick_value(args.cdt_progress_percent, "ALIYUN_CDT_PROGRESS_PERCENT"),
            usage=pick_value(args.cdt_usage, "ALIYUN_CDT_USAGE"),
            region_name=pick_value(args.cdt_region_name, "ALIYUN_CDT_REGION_NAME"),
            expires_at=pick_value(args.cdt_expires_at, "ALIYUN_CDT_EXPIRES_AT"),
            security_group_status=pick_value(args.cdt_security_group_status, "ALIYUN_CDT_SECURITY_GROUP_STATUS"),
        ),
        cn_traffic_usage=pick_value(args.cn_traffic_usage, "CN_TRAFFIC_USAGE"),
        intl_traffic_usage=pick_value(args.intl_traffic_usage, "INTL_TRAFFIC_USAGE"),
        traffic_limit_gb=float(pick_value(args.traffic_limit_gb, "TRAFFIC_LIMIT_GB") or "180"),
    )


def validate_access_key(cfg: InstanceConfig) -> None:
    placeholders = {"your_access_key_id", "your_access_key_secret", "replace_me", "changeme", "***", "null", "none"}
    ak_lower = cfg.access_key_id.lower()
    sk_lower = cfg.access_key_secret.lower()

    if ak_lower in placeholders or sk_lower in placeholders:
        raise ValueError(
            f"{cfg.name} AccessKey 看起来仍是占位符，请检查 secrets 是否已填入真实值。"
        )

    if len(cfg.access_key_id) < 12 or len(cfg.access_key_secret) < 16:
        raise ValueError(
            f"{cfg.name} AccessKey 长度异常，请确认没有多余引号、换行或被截断。"
        )

    if not cfg.access_key_id.startswith("LTAI"):
        raise ValueError(
            f"{cfg.name} AccessKeyId 格式异常。当前值应以 LTAI 开头，请确认 secrets 是否填写了 AccessKeyId。"
        )


def create_client(cfg: InstanceConfig) -> EcsClient:
    return EcsClient(
        open_api_models.Config(
            access_key_id=cfg.access_key_id,
            access_key_secret=cfg.access_key_secret,
            region_id=cfg.region_id,
            endpoint=f"ecs.{cfg.region_id}.aliyuncs.com",
        )
    )


def get_instance_status(client: EcsClient, cfg: InstanceConfig) -> str:
    req = ecs_models.DescribeInstanceStatusRequest(
        region_id=cfg.region_id,
        instance_id=[cfg.instance_id],
    )
    resp = client.describe_instance_status(req)
    statuses = resp.body.instance_statuses.instance_status
    if not statuses:
        raise RuntimeError(f"{cfg.name} 无法获取实例状态，请检查实例ID/地域配置")
    return statuses[0].status


def get_instance_snapshot(client: EcsClient, cfg: InstanceConfig) -> InstanceSnapshot:
    req = ecs_models.DescribeInstancesRequest(
        region_id=cfg.region_id,
        instance_ids=json.dumps([cfg.instance_id]),
    )
    resp = client.describe_instances(req)
    instances = resp.body.instances.instance
    if not instances:
        return InstanceSnapshot(instance_name="", public_ip="", expired_time="")

    instance = instances[0]
    public_ips = (
        instance.public_ip_address.ip_address
        if instance.public_ip_address and instance.public_ip_address.ip_address
        else []
    )
    public_ip = public_ips[0] if public_ips else ""
    return InstanceSnapshot(
        instance_name=instance.instance_name or "",
        public_ip=public_ip,
        expired_time=instance.expired_time or "",
    )


def start_instance(client: EcsClient, cfg: InstanceConfig) -> None:
    req = ecs_models.StartInstanceRequest(instance_id=cfg.instance_id)
    client.start_instance(req)


def stop_instance(client: EcsClient, cfg: InstanceConfig) -> None:
    req = ecs_models.StopInstanceRequest(
        instance_id=cfg.instance_id,
        force_stop=False,
        stopped_mode="StopCharging",
    )
    client.stop_instance(req)


def wait_for_status(
    client: EcsClient,
    cfg: InstanceConfig,
    expected_status: str,
    timeout_seconds: int = 600,
    interval_seconds: int = 10,
) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = get_instance_status(client, cfg)
        if status == expected_status:
            return status
        time.sleep(interval_seconds)
    final_status = get_instance_status(client, cfg)
    raise TimeoutError(
        f"{cfg.name} 超时未达到目标状态 {expected_status}，当前状态: {final_status}"
    )


def send_telegram(tg_bot_token: str, tg_chat_id: str, message: str) -> None:
    url = f"https://api.telegram.org/bot{tg_bot_token}/sendMessage"
    payload = {"chat_id": tg_chat_id, "text": message}
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()


def parse_usage_gb(usage_text: str) -> float | None:
    """
    从流量字符串提取已使用流量（GB）。
    示例:
    - "12.3GB / 180GB" -> 12.3
    - "180 G" -> 180.0
    - "102400MB / 180GB" -> 100.0
    """
    text = (usage_text or "").strip()
    if not text:
        return None

    match = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB|MB|KB|B)?", text, re.IGNORECASE)
    if not match:
        return None

    value = float(match.group(1))
    unit = (match.group(2) or "GB").upper()
    unit_factor = {
        "TB": 1024.0,
        "GB": 1.0,
        "MB": 1.0 / 1024.0,
        "KB": 1.0 / (1024.0 * 1024.0),
        "B": 1.0 / (1024.0 * 1024.0 * 1024.0),
    }
    return value * unit_factor.get(unit, 1.0)


def format_report_message(
    success: bool,
    now: datetime,
    desired_on_cfg: InstanceConfig,
    desired_off_cfg: InstanceConfig,
    final_on: str,
    final_off: str,
    action_logs: list[str],
    traffic_card: TrafficCardConfig,
    online_snapshot: InstanceSnapshot,
    cn_traffic_usage: str,
    intl_traffic_usage: str,
    traffic_limit_gb: float,
    traffic_guard_triggered: bool,
) -> str:
    title = "✅ ECS 自动轮换执行成功" if success else "❌ ECS 自动轮换执行异常"
    cn_status_emoji = "🟢" if "Running" in final_on or "Running" in final_off else "⚪"
    intl_status_emoji = "🟢" if "Running" in final_on or "Running" in final_off else "⚪"
    if desired_on_cfg.name == "国内站":
        cn_status_emoji = "🟢" if final_on == "Running" else "🔴"
        intl_status_emoji = "🟢" if final_off == "Running" else "🔴"
    else:
        intl_status_emoji = "🟢" if final_on == "Running" else "🔴"
        cn_status_emoji = "🟢" if final_off == "Running" else "🔴"

    summary = [
        title,
        "",
        "【执行摘要】",
        f"• 执行时间：{now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"• 调度策略：{desired_on_cfg.name} 开机，{desired_off_cfg.name} 关机",
        f"• 最终状态：{desired_on_cfg.name}={final_on}，{desired_off_cfg.name}={final_off}",
        f"• 运行状态：{cn_status_emoji} 国内站 / {intl_status_emoji} 国际站",
        "",
        "【当前在线实例】",
        f"• 实例名称：{online_snapshot.instance_name or desired_on_cfg.name}",
        f"• 公网 IP：{online_snapshot.public_ip or '未获取'}",
        f"• 实例地区：{traffic_card.region_name or desired_on_cfg.region_id}",
        f"• 实例ID：{desired_on_cfg.instance_id}",
        f"• 到期时间：{traffic_card.expires_at or online_snapshot.expired_time or '未配置'}",
        f"• 安全组状态：{traffic_card.security_group_status or '未配置'}",
    ]

    if traffic_card.cdt_name or traffic_card.progress_bar or traffic_card.usage:
        summary.extend(
            [
                "",
                "【流量信息】",
                f"• 套餐名称：{traffic_card.cdt_name or '未配置'}",
                f"• 使用进度：{traffic_card.progress_bar or '未配置'} {traffic_card.progress_percent}".rstrip(),
                f"• 已使用流量：{traffic_card.usage or '未配置'}",
            ]
        )
    summary.extend(
        [
            f"• 国内站流量：{cn_traffic_usage or '未配置'}",
            f"• 国际站流量：{intl_traffic_usage or '未配置'}",
            f"• 流量阈值：{traffic_limit_gb:g}GB",
        ]
    )
    if traffic_guard_triggered:
        summary.append("• 🚫 流量保护已触发：达到阈值的实例保持关机，待流量低于阈值后再自动开机")

    summary.extend(["", "【执行明细】"])
    summary.extend([f"• {line}" for line in action_logs])
    return "\n".join(summary)


def main() -> None:
    runtime = parse_args()
    cn_cfg, intl_cfg = runtime.cn, runtime.intl

    validate_access_key(cn_cfg)
    validate_access_key(intl_cfg)

    cn_client = create_client(cn_cfg)
    intl_client = create_client(intl_cfg)

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    even_hour = now.hour % 2 == 0

    desired_on_cfg = intl_cfg if even_hour else cn_cfg
    desired_on_client = intl_client if even_hour else cn_client
    desired_off_cfg = cn_cfg if even_hour else intl_cfg
    desired_off_client = cn_client if even_hour else intl_client

    logs: list[str] = []
    logs.append(f"当前小时={now.hour}")
    logs.append(f"计划: {desired_on_cfg.name} 开机, {desired_off_cfg.name} 关机")
    logs.append(f"流量阈值: {runtime.traffic_limit_gb:g}GB")

    cn_usage_gb = parse_usage_gb(runtime.cn_traffic_usage)
    intl_usage_gb = parse_usage_gb(runtime.intl_traffic_usage)
    desired_on_usage_gb = intl_usage_gb if even_hour else cn_usage_gb
    desired_on_usage_text = runtime.intl_traffic_usage if even_hour else runtime.cn_traffic_usage
    traffic_guard_triggered = (
        desired_on_usage_gb is not None and desired_on_usage_gb >= runtime.traffic_limit_gb
    )
    logs.append(f"国内站流量: {runtime.cn_traffic_usage or '未配置'}")
    logs.append(f"国际站流量: {runtime.intl_traffic_usage or '未配置'}")

    on_status = get_instance_status(desired_on_client, desired_on_cfg)
    logs.append(f"{desired_on_cfg.name} 当前状态: {on_status}")
    if traffic_guard_triggered:
        logs.append(
            f"{desired_on_cfg.name} 流量达到阈值（{desired_on_usage_text or f'{desired_on_usage_gb:.2f}GB'}），暂停开机"
        )
        if on_status == "Running":
            logs.append(f"执行关机(流量保护): {desired_on_cfg.name}")
            stop_instance(desired_on_client, desired_on_cfg)
            wait_for_status(desired_on_client, desired_on_cfg, "Stopped")
            logs.append(f"{desired_on_cfg.name} 已确认关机")
        else:
            logs.append(f"{desired_on_cfg.name} 已是关机状态，无需开机")
    else:
        if on_status != "Running":
            logs.append(f"执行开机: {desired_on_cfg.name}")
            start_instance(desired_on_client, desired_on_cfg)
            wait_for_status(desired_on_client, desired_on_cfg, "Running")
            logs.append(f"{desired_on_cfg.name} 已确认开机")
        else:
            logs.append(f"{desired_on_cfg.name} 已是开机状态")

    off_status = get_instance_status(desired_off_client, desired_off_cfg)
    logs.append(f"{desired_off_cfg.name} 当前状态: {off_status}")
    if off_status != "Stopped":
        logs.append(f"执行关机: {desired_off_cfg.name}")
        stop_instance(desired_off_client, desired_off_cfg)
        wait_for_status(desired_off_client, desired_off_cfg, "Stopped")
        logs.append(f"{desired_off_cfg.name} 已确认关机")
    else:
        logs.append(f"{desired_off_cfg.name} 已是关机状态")

    final_on = get_instance_status(desired_on_client, desired_on_cfg)
    final_off = get_instance_status(desired_off_client, desired_off_cfg)
    logs.append(f"最终状态: {desired_on_cfg.name}={final_on}, {desired_off_cfg.name}={final_off}")

    expected_on_status = "Stopped" if traffic_guard_triggered else "Running"
    success = final_on == expected_on_status and final_off == "Stopped"
    online_snapshot = get_instance_snapshot(desired_on_client, desired_on_cfg)
    message = format_report_message(
        success=success,
        now=now,
        desired_on_cfg=desired_on_cfg,
        desired_off_cfg=desired_off_cfg,
        final_on=final_on,
        final_off=final_off,
        action_logs=logs,
        traffic_card=runtime.traffic_card,
        online_snapshot=online_snapshot,
        cn_traffic_usage=runtime.cn_traffic_usage,
        intl_traffic_usage=runtime.intl_traffic_usage,
        traffic_limit_gb=runtime.traffic_limit_gb,
        traffic_guard_triggered=traffic_guard_triggered,
    )

    send_telegram(runtime.tg_bot_token, runtime.tg_chat_id, message)

    if not success:
        raise RuntimeError("最终状态不符合预期")


if __name__ == "__main__":
    try:
        main()
    except ClientException as exc:
        message = str(exc)
        if "InvalidCredentials" in message:
            raise RuntimeError(
                "ECS 自动轮换失败: AccessKey 无效。请检查 CN_* / INTL_* 的 AK/SK 是否为真实值，"
                "并确认没有包含额外空格、换行或引号。"
            ) from exc
        raise RuntimeError(f"ECS 自动轮换失败: {exc}") from exc
    except Exception as exc:
        # 此处仅打印错误，避免在异常路径重复发送消息导致噪音告警。
        raise RuntimeError(f"ECS 自动轮换失败: {exc}") from exc
