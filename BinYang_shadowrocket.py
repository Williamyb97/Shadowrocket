from pathlib import Path
import yaml

YAML_FILE = Path('/mnt/data/RHviJD9NYYiw(1).yaml')
OUT_FILE = Path('/mnt/data/Shadowrocket_BinYang_home_sync_grouped_local_filter.conf')

SUPPORTED_RULE_TYPES = {
    'DOMAIN', 'DOMAIN-SUFFIX', 'DOMAIN-KEYWORD',
    'IP-CIDR', 'IP-CIDR6', 'GEOIP', 'USER-AGENT',
    'URL-REGEX', 'DOMAIN-WILDCARD'
}
SKIP_RULE_TYPES = {'PROCESS-NAME'}

KEEP_POLICIES = {
    '🏠 国内直连', '🚀 出口节点', '🤖 ChatGPT', '💠 Gemini', '🧠 智能专区', '🌐 未知流量'
}
POLICY_REMAP = {
    '♻️ 延迟优选': '🚀 出口节点',
}

HEADER = """# Shadowrocket 通用分组配置 - 首页节点同步 + 本地节点筛选版
# 来源：由 Clash YAML 的 rules 提取转换
# 设计原则：
# 1. 🚀 出口节点 保留，但组内只指向 PROXY，因此跟随 Shadowrocket 首页当前选择节点。
# 2. 🤖 ChatGPT / 💠 Gemini 保留分组，但不直接放 PROXY，避免与 🚀 出口节点功能重复。
# 3. 🤖 ChatGPT / 💠 Gemini 保留 policy-regex-filter，用 Shadowrocket 已订阅/已存在的节点池进行本地筛选。
# 4. 不写 policy-path，不写 update-interval，不写死任何具体机场节点名。
# 5. 去除 ♻️ 延迟优选。
# 6. 国内工作与国内通信优先稳定；未知流量默认先选 🏠 国内直连。

[General]
bypass-system = true
skip-proxy = 127.0.0.1, localhost, *.local
dns-server = system

[Proxy Group]
🚀 出口节点 = select, PROXY
🤖 ChatGPT = select, 🚀 出口节点, policy-regex-filter=(GPT|ChatGPT|OpenAI|openai|chatgpt)
💠 Gemini = select, 🚀 出口节点, policy-regex-filter=(Gemini|gemini|Google AI|google ai)
🧠 智能专区 = select, 🤖 ChatGPT, 💠 Gemini, 🚀 出口节点
🏠 国内直连 = select, DIRECT
🌐 未知流量 = select, 🏠 国内直连, 🚀 出口节点

[Rule]
"""

def split_rule(rule: str):
    return [p.strip() for p in str(rule).strip().split(',')]

def convert_rule(rule: str):
    if not rule or not str(rule).strip():
        return None, 'empty'
    s = str(rule).strip()
    if s.startswith('#') or s.startswith(';'):
        return None, 'comment'

    parts = split_rule(s)
    if not parts:
        return None, 'empty'

    rtype = parts[0].upper()

    if rtype in SKIP_RULE_TYPES:
        return None, rtype

    if rtype == 'MATCH':
        policy = parts[1] if len(parts) >= 2 else '🌐 未知流量'
        policy = POLICY_REMAP.get(policy, policy)
        if policy not in KEEP_POLICIES:
            policy = '🌐 未知流量'
        return f'FINAL,{policy}', None

    if rtype == 'FINAL':
        policy = parts[1] if len(parts) >= 2 else '🌐 未知流量'
        policy = POLICY_REMAP.get(policy, policy)
        if policy not in KEEP_POLICIES:
            policy = '🌐 未知流量'
        return f'FINAL,{policy}', None

    if rtype not in SUPPORTED_RULE_TYPES:
        return None, rtype

    if len(parts) < 3:
        return None, 'bad_format'

    policy = POLICY_REMAP.get(parts[2], parts[2])
    if policy not in KEEP_POLICIES:
        policy = '🚀 出口节点'

    new_parts = parts[:]
    new_parts[2] = policy
    return ','.join(new_parts), None


def main():
    data = yaml.safe_load(YAML_FILE.read_text(encoding='utf-8'))
    rules = data.get('rules', []) or []

    out = [HEADER.rstrip()]
    seen = set()
    skipped = {}

    for rule in rules:
        converted, reason = convert_rule(rule)
        if converted:
            if converted not in seen:
                out.append(converted)
                seen.add(converted)
        else:
            skipped[reason] = skipped.get(reason, 0) + 1

    out_no_final = []
    for line in out:
        if not line.startswith('FINAL,'):
            out_no_final.append(line)
    out = out_no_final + ['FINAL,🌐 未知流量']

    summary = [
        '',
        '# ===== 生成摘要 =====',
        f'# 输入 Clash 规则数：{len(rules)}',
        f'# 输出 Shadowrocket 规则数：{sum(1 for x in out if x and not x.startswith("#") and not x.startswith("[") and "=" not in x)}',
        '# 跳过项：' + (', '.join(f'{k}:{v}' for k, v in sorted(skipped.items())) if skipped else '无'),
    ]
    OUT_FILE.write_text('\n'.join(out + summary) + '\n', encoding='utf-8')
    print(OUT_FILE)
    print('rules_in', len(rules), 'rules_out', sum(1 for x in out if x and not x.startswith('#') and not x.startswith('[') and '=' not in x), 'skipped', skipped)

if __name__ == '__main__':
    main()
