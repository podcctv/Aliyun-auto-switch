import argparse
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from alibabacloud_ecs20140526 import models as ecs_models
from alibabacloud_ecs20140526.client import Client as EcsClient
from alibabacloud_tea_openapi import models as open_api_models


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


def parse_args() -> RuntimeConfig:
    parser = argparse.ArgumentParser(description="Aliyun ECS 按小时交替开关机")

    parser.add_argument("--tg-bot-token", required=True)
    parser.add_argument("--tg-chat-id", required=True)

    parser.add_argument("--cn-access-key-id", required=True)
    parser.add_argument("--cn-access-key-secret", required=True)
    parser.add_argument("--cn-instance-id", required=True)
    parser.add_argument("--cn-region-id", required=True)

    parser.add_argument("--intl-access-key-id", required=True)
    parser.add_argument("--intl-access-key-secret", required=True)
    parser.add_argument("--intl-instance-id", required=True)
    parser.add_argument("--intl-region-id", required=True)

    args = parser.parse_args()

    cn = InstanceConfig(
        name="国内站",
        access_key_id=args.cn_access_key_id,
        access_key_secret=args.cn_access_key_secret,
        region_id=args.cn_region_id,
        instance_id=args.cn_instance_id,
    )
    intl = InstanceConfig(
        name="国际站",
        access_key_id=args.intl_access_key_id,
        access_key_secret=args.intl_access_key_secret,
        region_id=args.intl_region_id,
        instance_id=args.intl_instance_id,
    )

    return RuntimeConfig(
        tg_bot_token=args.tg_bot_token,
        tg_chat_id=args.tg_chat_id,
        cn=cn,
        intl=intl,
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


def start_instance(client: EcsClient, cfg: InstanceConfig) -> None:
    req = ecs_models.StartInstanceRequest(region_id=cfg.region_id, instance_id=cfg.instance_id)
    client.start_instance(req)


def stop_instance(client: EcsClient, cfg: InstanceConfig) -> None:
    req = ecs_models.StopInstanceRequest(
        region_id=cfg.region_id,
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


def main() -> None:
    runtime = parse_args()
    cn_cfg, intl_cfg = runtime.cn, runtime.intl
    cn_client = create_client(cn_cfg)
    intl_client = create_client(intl_cfg)

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    even_hour = now.hour % 2 == 0

    desired_on_cfg = intl_cfg if even_hour else cn_cfg
    desired_on_client = intl_client if even_hour else cn_client
    desired_off_cfg = cn_cfg if even_hour else intl_cfg
    desired_off_client = cn_client if even_hour else intl_client

    logs: list[str] = []
    logs.append(f"时间: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} (hour={now.hour})")
    logs.append(f"计划: {desired_on_cfg.name} 开机, {desired_off_cfg.name} 关机")

    on_status = get_instance_status(desired_on_client, desired_on_cfg)
    logs.append(f"{desired_on_cfg.name} 当前状态: {on_status}")
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

    success = final_on == "Running" and final_off == "Stopped"
    title = "✅ ECS 轮换成功" if success else "❌ ECS 轮换异常"
    message = title + "\n" + "\n".join(logs)

    send_telegram(runtime.tg_bot_token, runtime.tg_chat_id, message)

    if not success:
        raise RuntimeError("最终状态不符合预期")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # 此处仅打印错误，避免在异常路径重复发送消息导致噪音告警。
        raise RuntimeError(f"ECS 自动轮换失败: {exc}") from exc
