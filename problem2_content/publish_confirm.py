"""
题二专用：发布前人工确认模块

满足题目「如涉及对外发布，需在发布前加入人工确认」的硬性要求。
在推送 / 对外发布之前，把最终完整内容展示给运营人员：
    - [p] 确认发布（多渠道推送：飞书 + QQ 邮箱）
    - [e] 编辑后再发布
    - [r] 拒绝发布（不推送）
    - [q] 退出
"""
import sys


def publish_confirm(title: str, content: str) -> str:
    """发布前人工确认节点。

    Args:
        title: 报告/内容标题
        content: 待发布的完整内容（含发布计划 + 各平台正文）

    Returns:
        确认后待发布的内容字符串；若拒绝则返回空字符串。
    """
    print("\n" + "=" * 60)
    print("【发布前确认】以下内容即将对外发布，请最后确认")
    print("=" * 60)
    print(f"标题: {title}")
    print("-" * 60)
    print(content)
    print("-" * 60)

    while True:
        choice = input("操作 [p]确认发布  [e]编辑  [r]拒绝发布  [q]退出: ").strip().lower()
        if choice == "p":
            print(">>> 已确认发布，准备多渠道推送（飞书 + QQ 邮箱）\n")
            return content
        elif choice == "e":
            print(">>> 请输入修改后的完整内容（输入 END 单独一行结束）：")
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            edited = "\n".join(lines)
            print(">>> 已保存编辑后的内容，准备发布\n")
            return edited
        elif choice == "r":
            print(">>> 已拒绝发布，不推送\n")
            return ""
        elif choice == "q":
            print(">>> 已退出")
            sys.exit(0)
        else:
            print("无效输入，请重新选择")
