# -*- coding: utf-8 -*-
"""
laozhong-shengtu / ark_image.py —— 豆包 Seedream 出图（火山方舟 Ark）

用法：
  python ark_image.py "提示词" [选项]
  python ark_image.py --prompt-file 提示词.txt [选项]
  Get-Content 提示词.txt -Raw | python ark_image.py - [选项]

选项：
  --model   flash | 5.0 | 4.5 | pro        默认 flash
  --size    2K | 4K | 1024x1024 | 2560x1440 | 1728x2304 ...   默认 2K
  --name    输出文件名主题（不含扩展名）     默认 图_时间戳
  --out     输出目录                        默认 ~/ai图片
  --n       出几张（循环调用）               默认 1
  --watermark     打开「AI生成」水印（默认关闭）
  --open          出图后自动打开预览

约定：
  - key 从环境变量 ARK_API_KEY 读；读不到再去注册表 HKCU/HKLM 的 Environment 里找
  - 每张图旁边落一份 req_<名字>.json，改一个词就能重跑
  - 出图失败按 HTTP 状态码给中文结论，不猜
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

MODELS = {
    "flash": "doubao-seedream-5-0-flash-260915",
    "5.0": "doubao-seedream-5-0-260128",
    "4.5": "doubao-seedream-4-5-251128",
    "pro": "doubao-seedream-5-0-pro-260628",
}

DEFAULT_OUT = os.path.join(os.path.expanduser("~"), "ai图片")

HINTS = {
    "SetLimitExceeded": "账户额度/限流：到火山方舟控制台 → 开通管理 → 关闭「安全体验模式」或调高限额，再重跑。",
    "ModelNotOpen": "这个模型没开通：控制台开通该模型服务，或换 --model flash / 5.0。",
    "InvalidEndpointOrModel.NotFound": "模型 ID 不存在或无权限：核对模型名（本机可用清单见 SKILL.md 的模型矩阵）。",
    "InvalidParameter": "请求体非法：常见是中文/引号没按 UTF-8 传（走文件或 stdin，别用 PowerShell 单引号拼长中文）。",
    "AuthenticationError": "key 无效：检查 ARK_API_KEY。先按 api-self-check 走排查，别直接判 key 过期。",
    "InvalidApiKey": "key 无效：检查 ARK_API_KEY。先按 api-self-check 走排查，别直接判 key 过期。",
}


def die(msg: str) -> "None":
    print(msg, file=sys.stderr)
    sys.exit(1)


def get_key() -> str:
    key = os.environ.get("ARK_API_KEY", "").strip()
    if key:
        return key
    try:
        import winreg
    except ImportError:
        die("[ERR] 读不到 ARK_API_KEY（环境变量为空，且非 Windows 无法查注册表）")
    locations = (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )
    for root, sub in locations:
        try:
            with winreg.OpenKey(root, sub) as h:
                val = winreg.QueryValueEx(h, "ARK_API_KEY")[0].strip()
                if val:
                    return val
        except OSError:
            continue
    die("[ERR] 读不到 ARK_API_KEY：环境变量和 HKCU/HKLM Environment 里都没有。\n"
        "      设置方法：setx ARK_API_KEY \"你的key\"，然后重开终端。")


def post(payload: dict, key: str, timeout: int = 300) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(body).get("error", {})
        except Exception:
            err = {}
        code = err.get("code", "")
        msg = err.get("message", body[:300])
        hint = HINTS.get(code, "")
        print(f"[ERR] HTTP {e.code} {code}", file=sys.stderr)
        print(f"      {msg}", file=sys.stderr)
        if hint:
            print(f"      建议：{hint}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:  # 网络层
        die(f"[ERR] 请求没发出去：{e}\n      先测网络：curl -s -o NUL -w \"%{{http_code}}\" {ENDPOINT}")


def download(url: str, path: str) -> int:
    with urllib.request.urlopen(url, timeout=300) as r, open(path, "wb") as f:
        total = 0
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
    return total


def main() -> None:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("prompt", nargs="?", default=None, help="提示词；给 - 表示从 stdin 读")
    ap.add_argument("--prompt-file", default=None)
    ap.add_argument("--model", default="flash", help="flash | 5.0 | 4.5 | pro，或直接写完整模型 ID")
    ap.add_argument("--size", default="2K")
    ap.add_argument("--name", default=None)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--watermark", action="store_true")
    ap.add_argument("--open", dest="do_open", action="store_true")
    args = ap.parse_args()

    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read()
    elif args.prompt == "-":
        prompt = sys.stdin.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        die("[ERR] 没给提示词。用位置参数、--prompt-file，或管道 stdin。")

    prompt = prompt.strip()
    if not prompt:
        die("[ERR] 提示词是空的。")

    model = MODELS.get(args.model, args.model)
    key = get_key()
    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = args.name or f"图_{stamp}"

    payload = {
        "model": model,
        "prompt": prompt,
        "response_format": "url",
        "size": args.size,
        "stream": False,
        "watermark": bool(args.watermark),
    }

    saved = []
    for i in range(max(1, args.n)):
        tag = "" if args.n == 1 else f"_v{i + 1}"
        name = f"{base}{tag}"
        print(f"[..] {model} / {args.size} / watermark={payload['watermark']} -> {name}")
        res = post(payload, key)
        items = res.get("data") or []
        if not items:
            die(f"[ERR] 没有返回图片：{json.dumps(res, ensure_ascii=False)[:300]}")
        for j, item in enumerate(items):
            url = item.get("url")
            if not url:
                die(f"[ERR] 返回里没有 url：{json.dumps(item, ensure_ascii=False)[:300]}")
            suffix = ".jpeg" if "jpeg" in url.lower() or "jpg" in url.lower() else ".png"
            path = os.path.join(out_dir, f"{name}{'' if j == 0 else f'_{j + 1}'}{suffix}")
            size = download(url, path)
            saved.append(path)
            print(f"[OK] {path}  ({size / 1024 / 1024:.2f} MB, {item.get('size', '?')})")
        with open(os.path.join(out_dir, f"req_{name}.json"), "w", encoding="utf-8") as f:
            json.dump({**payload, "prompt": prompt}, f, ensure_ascii=False, indent=2)

    if args.do_open and saved:
        try:
            os.startfile(saved[0])  # type: ignore[attr-defined]
        except Exception:
            subprocess.run(["powershell.exe", "-Command", f"Invoke-Item '{saved[0]}'"])


if __name__ == "__main__":
    main()
