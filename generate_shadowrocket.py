#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a universal Shadowrocket .conf from a Clash YAML.

Final policy design:
- Keep [Proxy Group].
- Keep 🚀 出口节点, but set it to "select, PROXY" so it follows Shadowrocket's home-page selected node.
- Convert normal outbound rules that originally target 🚀 出口节点 to PROXY.
- Keep 🤖 ChatGPT / 💠 Gemini / 🧠 智能专区 / 🏠 国内直连 / 🌐 未知流量 groups.
- Keep ChatGPT/Gemini local policy-regex-filter, without policy-path/update-interval.
- Do not include concrete airport node names.
- Remove ♻️ 延迟优选.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional

try:
    import yaml
except ImportError as exc:
    raise SystemExit("Missing dependency: pip install pyyaml") from exc


PROXY_GROUP_BLOCK = """[Proxy Group]
🚀 出口节点 = select, PROXY
🤖 ChatGPT = select, 🚀 出口节点, policy-regex-filter=(GPT|ChatGPT|OpenAI|openai|chatgpt)
💠 Gemini = select, 🚀 出口节点, policy-regex-filter=(Gemini|gemini|Google AI|google ai)
🧠 智能专区 = select, 🤖 ChatGPT, 💠 Gemini, 🚀 出口节点
🏠 国内直连 = select, DIRECT
🌐 未知流量 = select, 🏠 国内直连, 🚀 出口节点
"""

HEADER = """# Shadowrocket 通用配置 - 保留代理组 + 出口规则同步首页节点
# 来源：由 Clash YAML 的 rules 提取转换
# 设计原则：
# 1. 保留 [Proxy Group]，不写死任何机场具体节点名。
# 2. 🚀 出口节点 分组保留，但组内只指向 PROXY，因此它跟随 Shadowrocket 首页当前选择节点。
# 3. 规则里原本指向 🚀 出口节点 的普通国外流量直接转换为 PROXY，完全同步首页节点。
# 4. 🤖 ChatGPT / 💠 Gemini / 🧠 智能专区 / 🏠 国内直连 / 🌐 未知流量 分组保留。
# 5. 🤖 ChatGPT / 💠 Gemini 保留本地 policy-regex-filter，用 Shadowrocket 已订阅/已存在节点池筛选。
# 6. 不写 policy-path，不写 update-interval，不保留 ♻️ 延迟优选。
# 7. 国内工作与国内通信优先稳定；未知流量默认先选 🏠 国内直连。

[General]
bypass-system = true
skip-proxy = 127.0.0.1, localhost, *.local
dns-server = system

"""


TARGET_MAP = {
    "🚀 出口节点": "PROXY",       # key point: sync with Shadowrocket home-page selected node
    "♻️ 延迟优选": "PROXY",
    "🤖 ChatGPT": "🤖 ChatGPT",
    "💠 Gemini": "💠 Gemini",
    "🧠 智能专区": "🧠 智能专区",
    "🏠 国内直连": "🏠 国内直连",
    "🌐 未知流量": "🌐 未知流量",
    "🚫 广告过滤": "REJECT",
    "DIRECT": "🏠 国内直连",
    "REJECT": "REJECT",
    "PROXY": "PROXY",
}


SUPPORTED_RULE_TYPES = {
    "DOMAIN",
    "DOMAIN-SUFFIX",
    "DOMAIN-KEYWORD",
    "IP-CIDR",
    "IP-CIDR6",
    "SRC-IP-CIDR",
    "GEOIP",
    "USER-AGENT",
    "URL-REGEX",
}


def normalize_target(target: str) -> str:
    target = target.strip()
    return TARGET_MAP.get(target, target)


def split_rule(rule: str) -> list[str]:
    # Clash rules in common rule-provider output are comma-separated.
    # Keep "no-resolve" or other options after the target.
    return [part.strip() for part in rule.split(",")]


def convert_rule(rule: str) -> Optional[str]:
    rule = str(rule).strip()
    if not rule or rule.startswith("#") or rule.startswith(";"):
        return None

    parts = split_rule(rule)
    if not parts:
        return None

    rule_type = parts[0].upper()

    # Clash MATCH is Shadowrocket FINAL
    if rule_type in {"MATCH", "FINAL"}:
        target = normalize_target(parts[1]) if len(parts) >= 2 else "🌐 未知流量"
        return f"FINAL,{target}"

    # iOS Shadowrocket generally does not need PROCESS-NAME from desktop Clash configs.
    if rule_type == "PROCESS-NAME":
        return None

    if rule_type not in SUPPORTED_RULE_TYPES:
        return None

    # Minimum: TYPE,VALUE,TARGET
    if len(parts) < 3:
        return None

    target = normalize_target(parts[2])
    # Preserve extra options such as no-resolve.
    converted_parts = parts[:2] + [target] + parts[3:]
    return ",".join(converted_parts)


def iter_clash_rules(config: dict) -> Iterable[str]:
    rules = config.get("rules", [])
    if not isinstance(rules, list):
        return []
    return (str(r) for r in rules)


def generate(input_yaml: Path, output_conf: Path) -> None:
    data = yaml.safe_load(input_yaml.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("The input YAML is not a valid Clash config object.")

    output_lines: list[str] = []
    output_lines.append(HEADER.rstrip())
    output_lines.append("")
    output_lines.append(PROXY_GROUP_BLOCK.rstrip())
    output_lines.append("")
    output_lines.append("[Rule]")

    seen: set[str] = set()
    skipped = 0

    for rule in iter_clash_rules(data):
        converted = convert_rule(rule)
        if converted is None:
            skipped += 1
            continue
        if converted not in seen:
            output_lines.append(converted)
            seen.add(converted)

    # Ensure a safe final fallback exists.
    if not any(line.startswith("FINAL,") for line in output_lines):
        output_lines.append("FINAL,🌐 未知流量")

    output_conf.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    print(f"Generated: {output_conf}")
    print(f"Rules written: {sum(1 for line in output_lines if line and not line.startswith('#'))}")
    print(f"Skipped unsupported/desktop-only rules: {skipped}")


def main(argv: list[str]) -> int:
    if len(argv) not in {2, 3}:
        print("Usage:")
        print("  python generate_shadowrocket_final_home_sync_groups.py input.yaml [output.conf]")
        return 2

    input_yaml = Path(argv[1])
    output_conf = Path(argv[2]) if len(argv) == 3 else Path("Shadowrocket_BinYang_FINAL_home_sync_groups.conf")

    if not input_yaml.exists():
        print(f"Input not found: {input_yaml}")
        return 1

    generate(input_yaml, output_conf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
