#!/usr/bin/env python3
"""Vast.ai GPU 租用管理工具"""

import os
import sys
import json
import subprocess
import requests
from typing import Optional

BASE_URL = "https://console.vast.ai/api/v0"
CONFIG_FILE = os.path.expanduser("~/.vast_config.json")


# ─── 配置管理 ────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)


def get_api_key() -> str:
    config = load_config()
    if config.get("api_key"):
        return config["api_key"]
    print("\n未找到 API Key，请先设置。")
    print("获取方式：登录 cloud.vast.ai -> Account -> API Key")
    key = input("请输入 API Key: ").strip()
    if not key:
        print("API Key 不能为空")
        sys.exit(1)
    config["api_key"] = key
    save_config(config)
    print("API Key 已保存。")
    return key


# ─── HTTP 请求 ────────────────────────────────────────────────────────────────

def headers() -> dict:
    return {"Authorization": f"Bearer {get_api_key()}", "Accept": "application/json"}


def api_get(path: str, params: dict = None) -> Optional[dict]:
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=headers(), params=params, timeout=15)
        if r.status_code == 401:
            print("认证失败，请检查 API Key。")
            return None
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print("网络连接失败。")
        return None
    except requests.exceptions.Timeout:
        print("请求超时，请重试。")
        return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None


def api_post(path: str, body: dict = None) -> Optional[dict]:
    try:
        r = requests.post(f"{BASE_URL}{path}", headers=headers(), json=body or {}, timeout=15)
        if r.status_code == 401:
            print("认证失败，请检查 API Key。")
            return None
        if r.status_code in (200, 201):
            return r.json() if r.text else {"ok": True}
        print(f"请求失败 [{r.status_code}]: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None


def api_put(path: str, body: dict = None) -> Optional[dict]:
    try:
        r = requests.put(f"{BASE_URL}{path}", headers=headers(), json=body or {}, timeout=15)
        if r.status_code == 401:
            print("认证失败，请检查 API Key。")
            return None
        if r.status_code in (200, 201):
            return r.json() if r.text else {"ok": True}
        print(f"请求失败 [{r.status_code}]: {r.text[:200]}")
        return None
    except Exception as e:
        print(f"请求失败: {e}")
        return None


def api_delete(path: str) -> bool:
    try:
        r = requests.delete(f"{BASE_URL}{path}", headers=headers(), timeout=15)
        if r.status_code in (200, 204):
            return True
        print(f"删除失败 [{r.status_code}]: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"请求失败: {e}")
        return False


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def hr():
    print("─" * 65)


def pause():
    input("\n按 Enter 返回主菜单...")


def fmt_price(offer: dict) -> str:
    price = offer.get("dph_total") or offer.get("dph_base") or offer.get("min_bid")
    if price is None:
        return "N/A"
    return f"${float(price):.3f}/hr"


def fmt_gpu(offer: dict) -> str:
    name = offer.get("gpu_name") or "未知GPU"
    count = offer.get("num_gpus") or 1
    return f"{count}x {name}"


def print_offer(idx: int, o: dict):
    oid = o.get("id") or "?"
    gpu = fmt_gpu(o)
    price = fmt_price(o)
    ram = o.get("gpu_ram") or ""
    cpu = o.get("cpu_name") or ""
    disk = o.get("disk_space") or ""
    loc = o.get("geolocation") or ""
    ram_str = f"  显存: {ram}MB" if ram else ""
    loc_str = f"  地区: {loc}" if loc else ""
    disk_str = f"  磁盘: {disk}GB" if disk else ""
    print(f"  [{idx}] {gpu}  价格: {price}{ram_str}{disk_str}{loc_str}")
    print(f"       ID: {oid}  CPU: {cpu}")


def print_instance(idx: int, inst: dict):
    iid = inst.get("id") or "?"
    gpu = fmt_gpu(inst)
    status = inst.get("actual_status") or inst.get("status_msg") or "未知"
    price = fmt_price(inst)
    ssh_host = inst.get("ssh_host") or ""
    ssh_port = inst.get("ssh_port") or ""
    ssh_str = f"  SSH: {ssh_host}:{ssh_port}" if ssh_host else ""
    print(f"  [{idx}] {gpu}  状态: {status}  价格: {price}{ssh_str}")
    print(f"       ID: {iid}")


# ─── 功能模块 ─────────────────────────────────────────────────────────────────

def search_offers(gpu_name: str = "") -> list:
    """搜索可用机器（拉取全部后本地过滤）"""
    query = {
        "verified": {"eq": True},
        "rentable": {"eq": True},
        "type": "on-demand",
        "order": [["dph_total", "asc"]],
        "limit": 500,
    }
    data = api_post("/bundles/", body=query)
    if data is None:
        return []
    offers = data.get("offers") or []
    if gpu_name:
        keyword = gpu_name.lower().replace(" ", "")
        offers = [o for o in offers if keyword in (o.get("gpu_name") or "").lower().replace(" ", "")]
    return offers


def get_default_image() -> str:
    config = load_config()
    return config.get("default_image") or "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"


def get_default_disk() -> int:
    config = load_config()
    return config.get("default_disk") or 20


def manage_images():
    """管理默认镜像"""
    print("\n=== 管理默认镜像 ===")
    hr()
    config = load_config()
    images = config.get("images") or []
    default_image = config.get("default_image") or "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"
    default_disk = config.get("default_disk") or 20

    while True:
        print(f"\n当前默认镜像: {default_image}")
        print(f"当前默认磁盘: {default_disk} GB")
        print("\n已保存的镜像：")
        if images:
            for i, img in enumerate(images, 1):
                marker = " [默认]" if img == default_image else ""
                print(f"  [{i}] {img}{marker}")
        else:
            print("  （无）")
        hr()
        print("  [a] 添加镜像")
        print("  [d] 删除镜像")
        print("  [s] 设为默认")
        print("  [k] 修改默认磁盘大小")
        print("  [0] 返回")

        op = input("选择操作: ").strip().lower()

        if op == "0":
            break
        elif op == "a":
            img = input("输入镜像地址（如 pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime）: ").strip()
            if img and img not in images:
                images.append(img)
                config["images"] = images
                save_config(config)
                print("已添加。")
        elif op == "d":
            v = input("输入要删除的编号: ").strip()
            if v.isdigit() and 1 <= int(v) <= len(images):
                removed = images.pop(int(v) - 1)
                config["images"] = images
                if config.get("default_image") == removed:
                    config["default_image"] = images[0] if images else ""
                    default_image = config["default_image"]
                save_config(config)
                print(f"已删除: {removed}")
        elif op == "s":
            if not images:
                print("请先添加镜像。")
                continue
            v = input("输入要设为默认的编号: ").strip()
            if v.isdigit() and 1 <= int(v) <= len(images):
                config["default_image"] = images[int(v) - 1]
                default_image = config["default_image"]
                save_config(config)
                print("已设为默认。")
        elif op == "k":
            v = input(f"输入默认磁盘大小（GB，当前 {default_disk}）: ").strip()
            try:
                config["default_disk"] = int(v)
                default_disk = config["default_disk"]
                save_config(config)
                print("已更新。")
            except ValueError:
                print("请输入数字。")


def rent_machine():
    """搜索并租用机器"""
    print("\n=== 租用机器 ===")
    hr()

    gpu_name = input("搜索 GPU 型号（如 RTX4090、A100、H100，直接回车显示全部）: ").strip()

    print("\n查询中...")
    offers = search_offers(gpu_name)

    if not offers:
        print("没有找到可用机器。")
        pause()
        return

    print(f"\n找到 {len(offers)} 台可用机器（按价格排序）：")
    hr()
    for i, o in enumerate(offers, 1):
        print_offer(i, o)
    hr()

    choice = input("选择要租用的机器编号（输入 0 取消）: ").strip()
    if not choice.isdigit() or int(choice) == 0:
        return
    idx = int(choice) - 1
    if idx < 0 or idx >= len(offers):
        print("编号无效。")
        pause()
        return

    offer = offers[idx]
    offer_id = offer.get("id")
    print(f"\n已选择: {fmt_gpu(offer)}  价格: {fmt_price(offer)}")
    hr()

    # 镜像选择
    default_image = get_default_image()
    default_disk = get_default_disk()
    config = load_config()
    images = config.get("images") or []

    print("选择 Docker 镜像：")
    print(f"  [0] 使用默认: {default_image}")
    for i, img in enumerate(images, 1):
        print(f"  [{i}] {img}")
    print(f"  [m] 手动输入")

    img_choice = input("选择（直接回车使用默认）: ").strip().lower()
    if not img_choice or img_choice == "0":
        image = default_image
    elif img_choice == "m":
        image = input("输入镜像地址: ").strip() or default_image
    elif img_choice.isdigit() and 1 <= int(img_choice) <= len(images):
        image = images[int(img_choice) - 1]
    else:
        image = default_image

    disk = input(f"磁盘空间（GB，默认 {default_disk}）: ").strip()
    try:
        disk = int(disk) if disk else default_disk
    except ValueError:
        disk = default_disk

    onstart = input("启动命令（可选，回车跳过）: ").strip()

    print(f"\n镜像: {image}  磁盘: {disk}GB")
    confirm = input("确认租用？(y/n): ").strip().lower()
    if confirm != "y":
        print("已取消。")
        pause()
        return

    body = {"image": image, "disk": disk}
    if onstart:
        body["onstart"] = onstart

    print("发送租用请求...")
    result = api_put(f"/asks/{offer_id}/", body)
    if result and result.get("success"):
        instance_id = result.get("new_contract")
        print(f"\n租用成功！实例 ID: {instance_id}")
        print("实例正在启动，可在 [2] 查看我的实例 中查看状态。")
    elif result:
        print(f"\n响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
    pause()


def list_my_instances():
    """查看我的实例"""
    print("\n=== 我的实例 ===")
    hr()

    print("查询中...")
    data = api_get("/instances/", params={"owner": "me"})
    if data is None:
        pause()
        return

    instances = data.get("instances") or []

    if not instances:
        print("当前没有租用中的实例。")
        pause()
        return

    print(f"共 {len(instances)} 个实例：")
    hr()
    for i, inst in enumerate(instances, 1):
        print_instance(i, inst)
    hr()
    pause()


def manage_instance():
    """管理实例（停止/删除/重启）"""
    print("\n=== 管理实例 ===")
    hr()

    print("查询中...")
    data = api_get("/instances/", params={"owner": "me"})
    if data is None:
        pause()
        return

    instances = data.get("instances") or []

    if not instances:
        print("当前没有租用中的实例。")
        pause()
        return

    print(f"共 {len(instances)} 个实例：")
    hr()
    for i, inst in enumerate(instances, 1):
        print_instance(i, inst)
    hr()

    choice = input("选择实例编号（输入 0 取消）: ").strip()
    if not choice.isdigit() or int(choice) == 0:
        return
    idx = int(choice) - 1
    if idx < 0 or idx >= len(instances):
        print("编号无效。")
        pause()
        return

    inst = instances[idx]
    iid = inst.get("id")

    print(f"\n选中: {fmt_gpu(inst)}  状态: {inst.get('actual_status')}  ID: {iid}")
    print("操作：")
    print("  [1] 删除实例（停止计费）")
    print("  [2] 暂停实例")
    print("  [3] 恢复实例")
    print("  [0] 取消")

    op = input("选择操作: ").strip()

    if op == "1":
        confirm = input("确认删除该实例？(y/n): ").strip().lower()
        if confirm == "y":
            if api_delete(f"/instances/{iid}/"):
                print("实例已删除。")
            else:
                print("删除失败。")

    elif op == "2":
        result = api_put(f"/instances/{iid}/", {"state": "stopped"})
        if result:
            print("暂停指令已发送。")

    elif op == "3":
        result = api_put(f"/instances/{iid}/", {"state": "running"})
        if result:
            print("恢复指令已发送。")

    pause()


def set_api_key():
    """修改 API Key"""
    print("\n=== 修改 API Key ===")
    config = load_config()
    current = config.get("api_key", "")
    if current:
        print(f"当前 API Key: {current[:8]}{'*' * 20}")
    key = input("输入新的 API Key（回车取消）: ").strip()
    if key:
        config["api_key"] = key
        save_config(config)
        print("API Key 已更新。")
    pause()


def update_program():
    """更新程序"""
    print("\n=== 更新程序 ===")
    hr()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        result = subprocess.run(["git", "pull"], cwd=script_dir, capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout.strip() or "已是最新版本。")
            if "Already up to date" not in result.stdout:
                print("\n更新成功，请重新启动程序以生效。")
        else:
            print(f"更新失败: {result.stderr.strip()}")
    except FileNotFoundError:
        print("未找到 git 命令。")
    pause()


# ─── 主菜单 ───────────────────────────────────────────────────────────────────

def main():
    while True:
        print()
        print("╔══════════════════════════════════╗")
        print("║     Vast.ai GPU 租用管理工具      ║")
        print("╠══════════════════════════════════╣")
        print("║  [1] 搜索并租用机器               ║")
        print("║  [2] 查看我的实例                 ║")
        print("║  [3] 管理实例（停止/删除）        ║")
        print("║  [4] 管理默认镜像                 ║")
        print("║  [5] 修改 API Key                 ║")
        print("║  [6] 更新程序                     ║")
        print("║  [0] 退出                         ║")
        print("╚══════════════════════════════════╝")

        choice = input("请选择: ").strip()

        if choice == "1":
            rent_machine()
        elif choice == "2":
            list_my_instances()
        elif choice == "3":
            manage_instance()
        elif choice == "4":
            manage_images()
        elif choice == "5":
            set_api_key()
        elif choice == "6":
            update_program()
        elif choice == "0":
            print("再见！")
            break
        else:
            print("无效选项，请重试。")


if __name__ == "__main__":
    main()
