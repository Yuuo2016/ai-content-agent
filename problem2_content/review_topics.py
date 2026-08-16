"""
题二专用：选题逐条人工审核模块

与 common/human_review.py（整段报告审核）不同，本模块对每个内容选题单独审核：
    支持 按条号编辑 / 按条号拒绝 / 通过完成 / 退出
    编辑(e)与拒绝(r)均不推送，只有最后按 p 完成审核时才整批进入内容生成。
"""
import sys

from common import feishu


def _print_topic(idx, topic, rejected=False):
    """打印单个选题的完整信息"""
    status = " [已拒绝]" if rejected else ""
    print(f"\n{idx}. {topic.get('title', '')}{status}")
    print(f"   目标人群: {topic.get('audience', '')} | 内容角度: {topic.get('angle', '')}")
    if topic.get("platform"):
        print(f"   建议平台: {topic.get('platform', '')}")
    if topic.get("rationale"):
        print(f"   选题理由: {topic.get('rationale', '')}")
    if topic.get("source"):
        print(f"   信息来源: {topic.get('source', '')}")
    if topic.get("url"):
        print(f"   来源链接: {topic.get('url', '')}")


def _edit_topic(topic):
    """对单个选题逐字段编辑，回车保持原样，返回新 dict"""
    print("\n>>> 进入编辑（每项输入新值后回车；直接回车=保持原样）:")
    fields = ["title", "audience", "angle", "platform", "rationale"]
    labels = {
        "title": "标题",
        "audience": "目标人群",
        "angle": "内容角度",
        "platform": "建议平台",
        "rationale": "选题理由",
    }
    new_topic = dict(topic)
    for f in fields:
        prompt = f"    {labels[f]} [{topic.get(f, '')}]: "
        val = input(prompt).strip()
        if val:
            new_topic[f] = val
    print(">>> 已保存对该选题的编辑")
    return new_topic


def review_topics(topics):
    """逐条人工审核选题列表。

    Args:
        topics: [{title, audience, angle, platform, rationale, source, url}]

    Returns:
        最终保留的选题列表（含被编辑过的）；按 p 完成时返回，进入后续内容生成。
        e/r 操作不推送。
    """
    wl = [dict(t) for t in topics]           # 可修改的工作副本
    active = [True] * len(wl)                 # 是否保留

    print("\n" + "=" * 60)
    print("【选题审核】以下为候选选题，请逐条审阅")
    print("操作说明: [p]完成并进入生成  [e]输入条号编辑  [r]输入条号拒绝  [q]退出")
    print("提示: 编辑(e)与拒绝(r)均不推送，仅按 p 完成时统一进入内容生成")
    print("=" * 60)

    # 先完整展示每个选题的内容
    print("\n" + "#" * 60)
    print("📋 当日候选选题详情（按顺序展示每个完整内容）")
    print("#" * 60)
    for i, t in enumerate(wl, 1):
        _print_topic(i, t)
        print()

    # 再按顺序标号输出当日候选清单
    print("\n" + "-" * 60)
    print("📌 当日候选选题清单（共 %d 条）" % len(wl))
    print("-" * 60)
    for i, t in enumerate(wl, 1):
        print(f"  {i}. {t.get('title', '')[:45]} | 平台: {t.get('platform', '')}"
              + (" [已拒绝]" if not active[i - 1] else ""))
    print("-" * 60)

    while True:
        # 每次循环都重新展示当前全部状态，并给出操作按钮
        print("\n" + "-" * 60)
        print("当前候选选题清单：")
        for i, t in enumerate(wl, 1):
            print(f"  {i}. {t.get('title', '')[:45]} | 平台: {t.get('platform', '')}"
                  + (" [已拒绝]" if not active[i - 1] else ""))
        print("-" * 60)

        choice = input("操作 [p]完成并进入生成  [e]编辑  [r]拒绝  [q]退出: ").strip().lower()

        if choice == "p":
            final = [wl[i] for i in range(len(wl)) if active[i]]
            print("\n>>> 审核完成，保留的全部选题（含编辑过的）")
            print("=" * 60)
            print(f"📌 最终选题清单（共 {len(final)} 条）")
            print("=" * 60)
            for i, t in enumerate(final, 1):
                _print_topic(i, t)
                print()
            return final

        elif choice == "e":
            num = input(">>> 输入要编辑的条号: ").strip()
            if not num.isdigit() or not (1 <= int(num) <= len(wl)):
                print("      无效条号，请重新操作")
                continue
            idx = int(num) - 1
            _print_topic(idx + 1, wl[idx])
            wl[idx] = _edit_topic(wl[idx])
            active[idx] = True

        elif choice == "r":
            num = input(">>> 输入要拒绝的条号: ").strip()
            if not num.isdigit() or not (1 <= int(num) <= len(wl)):
                print("      无效条号，请重新操作")
                continue
            idx = int(num) - 1
            active[idx] = False
            print(f">>> 已拒绝第 {int(num)} 条")

        elif choice == "q":
            print(">>> 已退出")
            sys.exit(0)

        else:
            print("无效输入，请重新选择")
