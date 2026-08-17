"""
题二：内容运营 Agent — Streamlit Web 界面（完整版·交互增强）

运行方式：
    streamlit run app.py

功能：
    - 输入内容主题，一键启动7步流程
    - 实时展示每步进度和结果
    - 【新】信息源不满意可重新搜索
    - 【新】选题审核改为可编辑（标题/平台/人群/角度均可修改）
    - 【新】发布内容可编辑（小红书/公众号内容可修改后再推送）
    - 发布前确认 + 多渠道推送（飞书 + QQ邮箱）
    - 生成 Word 文档下载

修复点：
    - 使用 session_state 管理工作流步骤，防止无限刷新
    - 不在每次 rerun 时把 widget 返回值写回 session_state
    - 绝对导入解决模块找不到问题
"""
import sys
import os
from datetime import datetime

import streamlit as st

# 自动加载 .env 环境变量
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import llm
from common import push
from problem2_content.sources import fetch_all, fetch_hot_topics
from problem2_content.main import (
    collect_topics,
    generate_multi_platform,
    generate_publish_plan,
    save_to_word,
)


def init_page():
    """初始化页面"""
    st.set_page_config(
        page_title="内容运营 Agent",
        page_icon="📝",
        layout="wide",
    )
    st.title("📝 题二：内容运营 Agent")
    st.markdown("---")
    st.markdown("自动发现热门话题 → 抓取真实资讯 → AI 生成选题 → 生成多平台内容 → 发布计划 → 多渠道推送")


def init_session_state():
    """初始化 session_state（防止无限刷新的关键）"""
    defaults = {
        "step": 0,
        "keyword": "AI 产品出海增长",
        "hot_topics": [],
        "source_items": [],
        "topics": [],
        "final_topics": [],
        "versions_map": {},
        "plan": "",
        "pushed": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def show_sidebar():
    """侧边栏配置与环境检查"""
    with st.sidebar:
        st.header("⚙️ 配置")
        st.text_input(
            "内容主题",
            value=st.session_state.keyword,
            key="keyword_input",
            help="输入后点击「开始运行」"
        )

        st.markdown("---")
        st.markdown("### 环境检查")

        api_key = os.getenv("LLM_API_KEY", "")
        if api_key and api_key != "sk-xxxxxxxxxxxxxxxx":
            st.success("✅ LLM API Key 已配置")
        else:
            st.error("❌ LLM API Key 未配置，请在 .env 中设置")

        feishu = os.getenv("FEISHU_WEBHOOK", "")
        if feishu:
            st.success("✅ 飞书 Webhook 已配置")
        else:
            st.warning("⚠️ 飞书 Webhook 未配置")

        email = os.getenv("EMAIL_USER", "")
        if email:
            st.success("✅ QQ 邮箱已配置")
        else:
            st.warning("⚠️ QQ 邮箱未配置")

        st.markdown("---")
        st.caption("题二：内容运营 Agent v3.0")
        st.caption(f"当前步骤: {st.session_state.step}/3")


# ============================================================
# 步骤 0：开始按钮
# ============================================================
def step0_start():
    """开始运行按钮"""
    if st.session_state.step == 0:
        st.header("🚀 准备就绪")
        st.markdown("点击下方按钮启动内容运营工作流（7 步自动化流程）")

        steps_display = [
            "1️⃣ 自动发现热门话题",
            "2️⃣ 抓取真实信息源（可重新搜索）",
            "3️⃣ AI 生成选题",
            "4️⃣ 选题审核（可编辑标题/平台/人群/角度）",
            "5️⃣ AI 生成多平台内容（可编辑后再发布）",
            "6️⃣ 生成发布计划",
            "7️⃣ 发布前确认 + 多渠道推送",
        ]
        for s in steps_display:
            st.markdown(f"  - {s}")

        if st.button("🚀 开始运行", type="primary", width="stretch"):
            st.session_state.keyword = st.session_state.keyword_input
            st.session_state.step = 1
            st.rerun()


# ============================================================
# 步骤 1：自动发现热门话题 + 抓取真实信息源
# ============================================================
def step1_hot_topics_and_sources():
    """热门话题 + 真实资讯

    【新功能】信息源不满意可点击「重新搜索」按钮重新抓取
    """
    # Step 1: 热门话题
    st.header("1️⃣ 自动发现热门话题")
    if not st.session_state.hot_topics:
        with st.spinner("正在抓取知乎热榜 / 微博热搜 / 百度热搜 / HN ..."):
            st.session_state.hot_topics = fetch_hot_topics()

    st.success(f"发现 {len(st.session_state.hot_topics)} 个热门话题")
    if st.session_state.hot_topics:
        df_data = []
        for ht in st.session_state.hot_topics[:15]:
            df_data.append({
                "来源": ht.get("source", ""),
                "标题": ht.get("title", "")[:50],
                "链接": ht.get("url", ""),
            })
        st.dataframe(df_data, width="stretch", hide_index=True)

    # Step 2: 真实资讯
    st.header("2️⃣ 抓取真实信息源")
    if not st.session_state.source_items:
        with st.spinner("正在抓取 Hacker News / TechCrunch / InfoQ / GitHub ..."):
            st.session_state.source_items = fetch_all(max_items=20)

    st.success(f"共抓取到 {len(st.session_state.source_items)} 条真实资讯")
    if st.session_state.source_items:
        df_data = []
        for it in st.session_state.source_items[:10]:
            df_data.append({
                "来源": it.get("source", ""),
                "标题": it.get("title", "")[:40],
            })
        st.dataframe(df_data, width="stretch", hide_index=True)

    # 【新功能】重新搜索按钮
    st.markdown("---")
    st.markdown("##### 💡 对信息源不满意？可重新搜索")
    col_re, col_next = st.columns([1, 2])
    with col_re:
        if st.button("🔄 重新搜索信息源", help="清空当前结果，重新抓取热门话题和真实资讯"):
            st.session_state.hot_topics = []
            st.session_state.source_items = []
            st.rerun()
    with col_next:
        if st.session_state.step == 1:
            if st.button("➡️ 生成选题", type="primary", width="stretch"):
                st.session_state.step = 2
                st.rerun()


# ============================================================
# 步骤 2：AI 生成选题 + 选题审核（可编辑）
# ============================================================
def step2_topics_and_review():
    """AI 生成选题 + 网页交互审核

    【新功能】选题审核改为可编辑：
    - 标题可编辑（text_input）
    - 平台可编辑（text_input）
    - 目标人群可编辑（text_input）
    - 内容角度可编辑（text_input）
    - 选题理由可编辑（text_area）
    """
    # Step 3: AI 生成选题
    st.header("3️⃣ AI 基于热门话题 + 真实信息生成选题")
    if not st.session_state.topics:
        with st.spinner(f"AI 正在基于主题「{st.session_state.keyword}」生成选题..."):
            st.session_state.topics = collect_topics(
                st.session_state.source_items,
                st.session_state.hot_topics,
                st.session_state.keyword,
                count=5,
            )
    st.success(f"生成 {len(st.session_state.topics)} 个选题")

    # Step 4: 选题审核（可编辑）
    st.header("4️⃣ 选题审核（可编辑）")
    st.markdown("✏️ 可直接修改选题的标题、平台、人群、角度等，修改后点击下方按钮保存")

    # 可编辑选题列表
    checked_count = 0
    for i, t in enumerate(st.session_state.topics):
        with st.expander(f"选题 {i+1}", expanded=True):
            col1, col2 = st.columns([0.3, 4])
            with col1:
                checked = st.checkbox("保留", value=True, key=f"check_{i}")
            with col2:
                if checked:
                    checked_count += 1

            # 可编辑字段
            col_a, col_b = st.columns(2)
            with col_a:
                new_title = st.text_input(
                    "标题",
                    value=t.get("title", ""),
                    key=f"edit_title_{i}",
                )
                new_audience = st.text_input(
                    "目标人群",
                    value=t.get("audience", ""),
                    key=f"edit_audience_{i}",
                )
            with col_b:
                new_platform = st.text_input(
                    "平台建议",
                    value=t.get("platform", "公众号"),
                    key=f"edit_platform_{i}",
                )
                new_angle = st.text_input(
                    "内容角度",
                    value=t.get("angle", ""),
                    key=f"edit_angle_{i}",
                )

            new_rationale = st.text_area(
                "选题理由",
                value=t.get("rationale", ""),
                key=f"edit_rationale_{i}",
                height=80,
            )

            if t.get("source"):
                st.caption(f"📋 原始来源: {t.get('source', '')} | 链接: {t.get('url', '')}")

    st.info(f"当前保留 {checked_count} 个选题")

    # 下一步按钮
    if checked_count > 0:
        if st.session_state.step == 2:
            if st.button("➡️ 保存并生成多平台内容", type="primary"):
                # 收集勾选的选题，并应用用户的编辑
                final = []
                for i, t in enumerate(st.session_state.topics):
                    if st.session_state[f"check_{i}"]:
                        # 应用编辑后的值
                        edited = dict(t)
                        edited["title"] = st.session_state[f"edit_title_{i}"]
                        edited["audience"] = st.session_state[f"edit_audience_{i}"]
                        edited["platform"] = st.session_state[f"edit_platform_{i}"]
                        edited["angle"] = st.session_state[f"edit_angle_{i}"]
                        edited["rationale"] = st.session_state[f"edit_rationale_{i}"]
                        final.append(edited)
                st.session_state.final_topics = final
                st.session_state.step = 3
                st.rerun()
    else:
        st.warning("请至少保留一个选题")


# ============================================================
# 步骤 3：生成多平台内容 + 发布计划 + 推送
# ============================================================
def step3_content_plan_publish():
    """AI 生成多平台内容 + 发布计划 + 推送

    【新功能】发布内容可编辑：
    - 公众号版本内容可在 text_area 中直接修改
    - 小红书版本内容可在 text_area 中直接修改
    - 修改后的内容在推送时自动应用
    """
    # Step 5: 生成多平台内容
    st.header("5️⃣ AI 生成多平台内容（可编辑）")
    st.markdown("✏️ 可直接在文本框中修改内容，修改后点击「确认发布」时将使用修改后的版本")

    if not st.session_state.versions_map:
        progress = st.progress(0)
        for idx, t in enumerate(st.session_state.final_topics):
            st.markdown(f"**正在为「{t.get('title')}」生成内容...**")
            with st.spinner("生成中..."):
                versions = generate_multi_platform(t)
                st.session_state.versions_map[t.get("title", "")] = versions
            progress.progress((idx + 1) / len(st.session_state.final_topics))
        st.success("所有内容生成完成！请检查并修改下方内容")

    # 展示可编辑的内容
    for idx, t in enumerate(st.session_state.final_topics):
        title = t.get("title", "")
        versions = st.session_state.versions_map.get(title, {})

        st.markdown(f"#### 📝 选题：{title}")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 📱 公众号版本")
            st.text_area(
                "公众号内容",
                value=versions.get("公众号", ""),
                height=300,
                key=f"edit_wechat_{idx}",
                label_visibility="collapsed",
            )
        with col2:
            st.markdown("##### 📕 小红书版本")
            st.text_area(
                "小红书内容",
                value=versions.get("小红书", ""),
                height=300,
                key=f"edit_xhs_{idx}",
                label_visibility="collapsed",
            )

    # Step 6: 发布计划
    st.header("6️⃣ 生成发布计划")
    if not st.session_state.plan:
        st.session_state.plan = generate_publish_plan(
            st.session_state.final_topics,
            st.session_state.versions_map,
        )
    # 发布计划也可编辑
    edited_plan = st.text_area(
        "发布计划（可编辑）",
        value=st.session_state.plan,
        height=250,
        key="edit_plan",
        label_visibility="collapsed",
    )

    # Step 7: 发布前确认 + 推送
    st.header("7️⃣ 发布前确认 & 推送")
    st.markdown("⚠️ 推送时将使用上方文本框中**修改后**的内容")

    # 组装完整报告（应用用户编辑后的内容）
    report = edited_plan + "\n===== 内容正文 =====\n"
    for idx, t in enumerate(st.session_state.final_topics):
        title = t.get("title", "")
        report += f"\n【{title}】\n"
        # 使用用户编辑后的内容
        wechat_content = st.session_state.get(f"edit_wechat_{idx}", "")
        xhs_content = st.session_state.get(f"edit_xhs_{idx}", "")
        if wechat_content:
            report += f"\n-- 公众号版本 --\n{wechat_content}\n"
        if xhs_content:
            report += f"\n-- 小红书版本 --\n{xhs_content}\n"

    with st.expander("查看完整报告内容（推送内容预览）", expanded=False):
        st.text(report)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("✅ 确认发布", type="primary"):
            with st.spinner("正在推送（飞书 + QQ邮箱）..."):
                try:
                    results = push.push_all("内容运营报告", report)
                    for channel, res in results.items():
                        if channel == "企业微信":
                            continue
                        status = "✅ 成功" if res.get("ok") else "❌ 失败"
                        st.write(f"**{channel}**: {status} — {res.get('detail')}")
                    st.success("推送完成！")
                    st.session_state.pushed = True
                except Exception as e:
                    st.error(f"推送失败: {e}")

            # 生成 Word 文档
            try:
                doc_path = f"output/content_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
                os.makedirs("output", exist_ok=True)
                save_to_word("内容运营报告", report, doc_path)
                with open(doc_path, "rb") as f:
                    st.download_button(
                        label="📥 下载 Word 文档",
                        data=f.read(),
                        file_name=os.path.basename(doc_path),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                st.success(f"Word 文档已生成: {doc_path}")
            except Exception as e:
                st.error(f"Word 生成失败: {e}")

    with col2:
        if st.button("🔄 重新开始"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


# ============================================================
# 主函数
# ============================================================
def main():
    init_page()
    init_session_state()
    show_sidebar()

    if st.session_state.step == 0:
        step0_start()
    elif st.session_state.step == 1:
        step1_hot_topics_and_sources()
    elif st.session_state.step == 2:
        step2_topics_and_review()
    elif st.session_state.step == 3:
        step3_content_plan_publish()


if __name__ == "__main__":
    main()
