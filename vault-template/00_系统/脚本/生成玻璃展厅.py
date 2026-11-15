# -*- coding: utf-8 -*-
"""重新生成 00_系统/工作台-玻璃展厅.html

数据口径与「生成知识库导航页.py」一致：使用 git 首次入库日期。
只替换 HTML 中的 FLUID_GLASS_CONFIG 与快照日期，保留界面/交互/跳转逻辑。

用法（在 vault 根目录执行）：
    python "00_系统/脚本/生成玻璃展厅.py"
"""
import subprocess
import sys
import os
import re
import json
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)

HTML = os.path.join("00_系统", "工作台-玻璃展厅.html")
TEMPLATE = os.path.join("00_系统", "模板", "玻璃展厅模板.html")

G = ["git", "-c", "core.quotepath=false"]
EXCLUDE_TOP = {"00_系统", "00_Inbox", "template", ".claude", "private"}
EXCLUDE_BASE = {"README", "CLAUDE"}


def git_files_and_dates():
    files = subprocess.run(G + ["ls-files", "--cached", "--others", "--exclude-standard", "*.md"], capture_output=True, text=True,
                           encoding="utf-8").stdout.splitlines()
    out = subprocess.run(G + ["log", "--diff-filter=A", "--reverse", "--format=@@%ad",
                              "--date=short", "--name-only", "--no-renames"],
                         capture_output=True, text=True, encoding="utf-8").stdout
    add, cur = {}, None
    for line in out.splitlines():
        if line.startswith("@@"):
            cur = line[2:].strip()
        elif line.strip() and cur:
            add.setdefault(line.strip(), cur)
    return files, add


def fallback_date(p):
    try:
        return datetime.date.fromtimestamp(os.path.getctime(p))
    except Exception:
        return datetime.date.today()


def base(p):
    return os.path.splitext(os.path.basename(p))[0]


def stats(files, add):
    today = datetime.date.today()
    month = today.strftime("%Y-%m")
    last_month_day = today.replace(day=1) - datetime.timedelta(days=1)
    last_month = last_month_day.strftime("%Y-%m")
    week_start = today - datetime.timedelta(days=6)
    prev_week_start = week_start - datetime.timedelta(days=7)
    prev_week_end = week_start - datetime.timedelta(days=1)

    items = []
    for f in files:
        top = f.split("/")[0]
        if top in EXCLUDE_TOP or base(f) in EXCLUDE_BASE:
            continue
        if base(f).endswith("-MOC"):
            continue
        d = add.get(f)
        if not d:
            d = fallback_date(f).isoformat()
        items.append((datetime.date(*map(int, d.split("-"))), f))

    def cnt(pred):
        return sum(1 for d, f in items if pred(d, f))

    def month_cnt(prefix=""):
        return cnt(lambda d, f: d.strftime("%Y-%m") == month and f.startswith(prefix))

    def last_month_cnt(prefix=""):
        return cnt(lambda d, f: d.strftime("%Y-%m") == last_month and f.startswith(prefix))

    def total_cnt(prefix=""):
        return cnt(lambda d, f: f.startswith(prefix))

    def week_cnt():
        return cnt(lambda d, f: d >= week_start)

    def prev_week_cnt():
        return cnt(lambda d, f: prev_week_start <= d <= prev_week_end)

    def growth(cur, prev):
        if prev <= 0:
            return 0
        return max(-99, min(999, round((cur - prev) / prev * 100)))

    def rate(cur, base):
        if base <= 0:
            return 0
        return max(0, min(999, round(cur / base * 100)))

    total = len(items)
    llm = total_cnt("AI大模型/")
    agent = total_cnt("AI大模型/Agent/")
    rag = total_cnt("AI大模型/rag/")
    interview = total_cnt("工作/面试收集/")
    work = total_cnt("工作/")
    month_new = month_cnt()
    week_new = week_cnt()

    def folder_change(prefix):
        cur = month_cnt(prefix)
        base = total_cnt(prefix) - cur
        return rate(cur, base)

    return {
        "total": total,
        "llm": llm,
        "agent": agent,
        "rag": rag,
        "interview": interview,
        "work": work,
        "month": month_new,
        "week": week_new,
        "total_change": folder_change(""),
        "llm_change": folder_change("AI大模型/"),
        "agent_change": folder_change("AI大模型/Agent/"),
        "rag_change": folder_change("AI大模型/rag/"),
        "interview_change": folder_change("工作/面试收集/"),
        "work_change": folder_change("工作/"),
        "month_change": rate(month_new, total - month_new),
        "week_change": rate(week_new, total - week_new),
        "today": today.isoformat(),
    }


CARDS = [
    ("notes-total", "全库笔记", "OBSIDIAN VAULT", "total", "total_change", 1.7, 0.92, 1.02, 0.82),
    ("llm-notes", "AI 大模型", "LLM & AGENT", "llm", "llm_change", 4.9, 0.84, 1.08, 0.80),
    ("agent-notes", "Agent", "AGENT ENGINEERING", "agent", "agent_change", 8.4, 0.76, 0.98, 0.72),
    ("rag-notes", "RAG", "RETRIEVAL", "rag", "rag_change", 12.1, 0.88, 1.05, 0.86),
    ("interview", "面试题", "INTERVIEW", "interview", "interview_change", 3.3, 0.90, 1.00, 0.78),
    ("work-notes", "工作笔记", "WORK", "work", "work_change", 6.6, 0.82, 1.06, 0.84),
    ("month-new", "本月新增", "THIS MONTH", "month", "month_change", 9.2, 0.78, 1.03, 0.75),
    ("week-new", "近 7 天", "LAST 7 DAYS", "week", "week_change", 11.4, 0.86, 1.04, 0.83),
]


def build_config(s):
    cards = []
    for key, label, eyebrow, value_key, change_key, seed, speed, intensity, pointer in CARDS:
        cards.append({
            "key": key,
            "label": label,
            "eyebrow": eyebrow,
            "value": str(s[value_key]),
            "unit": "篇",
            "change": s[change_key],
            "seed": seed,
            "speed": speed,
            "intensity": intensity,
            "pointer": pointer,
            "preset": "cyan",
            "a": "#00e7d2",
            "b": "#3cc8ff",
            "c": "#075f68",
            "surface": 0.08,
            "chart": {"enabled": False},
        })
    return {
        "storageKey": "obsidian_fluid_glass_dashboard",
        "quality": "auto",
        "interaction": True,
        "cards": cards,
    }


def main():
    files, add = git_files_and_dates()
    s = stats(files, add)
    config = build_config(s)

    src = HTML if os.path.exists(HTML) else TEMPLATE
    if not os.path.exists(src):
        print("找不到展厅 HTML：", HTML, "或模板：", TEMPLATE)
        return 1

    with open(src, "r", encoding="utf-8") as f:
        html = f.read()

    payload = "window.FLUID_GLASS_CONFIG = " + json.dumps(config, ensure_ascii=False) + ";"
    pattern = re.compile(r"window\.FLUID_GLASS_CONFIG\s*=\s*\{.*?\};", re.S)
    if not pattern.search(html):
        print("HTML 中未找到 FLUID_GLASS_CONFIG，跳过替换")
        return 1
    html = pattern.sub(lambda m: payload, html, count=1)

    html = re.sub(r"数据快照\s*\d{4}-\d{2}-\d{2}", "数据快照 " + s["today"], html)
    html = re.sub(r"(数据快照\s*\d{4}-\d{2}-\d{2})", r"\1", html)

    with open(HTML, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    print("已生成 %s：全库 %d · AI大模型 %d · Agent %d · RAG %d · 面试 %d · 工作 %d · 本月 %d · 近7天 %d"
          % (HTML, s["total"], s["llm"], s["agent"], s["rag"], s["interview"], s["work"], s["month"], s["week"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
