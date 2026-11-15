# -*- coding: utf-8 -*-
"""重新生成 00_系统/知识库导航页.md

用法（在 vault 根目录执行）：
    python "00_系统/脚本/生成知识库导航页.py"

收录时间口径：git 首次入库日期（git log --diff-filter=A）。
"""
import subprocess, sys, os, collections, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
OUT = "00_系统/知识库导航页.md"
G = ["git", "-c", "core.quotepath=false"]

files = subprocess.run(G + ["ls-files", "--cached", "--others", "--exclude-standard", "*.md"], capture_output=True, text=True, encoding="utf-8").stdout.splitlines()
out = subprocess.run(G + ["log", "--diff-filter=A", "--reverse", "--format=@@%ad", "--date=short",
                          "--name-only", "--no-renames"], capture_output=True, text=True, encoding="utf-8").stdout
add, cur = {}, None
for line in out.splitlines():
    if line.startswith("@@"):
        cur = line[2:].strip()
    elif line.strip() and cur:
        add.setdefault(line.strip(), cur)

EXCLUDE_TOP = {"00_系统", "00_Inbox", "template", ".claude", "private"}
EXCLUDE_BASE = {"README", "CLAUDE"}

def fallback_date(p):
    try:
        return datetime.date.fromtimestamp(os.path.getctime(p))
    except Exception:
        return datetime.date.today()


def base(p): return os.path.splitext(os.path.basename(p))[0]
def dt(s): return datetime.date(*map(int, s.split("-")))

notes = []
for f in files:
    top = f.split("/")[0]
    if top in EXCLUDE_TOP or base(f) in EXCLUDE_BASE: continue
    if base(f).endswith("-MOC") or base(f) == "MOC": continue
    if f in add: notes.append((dt(add[f]), f))
    else: notes.append((fallback_date(f), f))

TODAY = datetime.date.today()
def month_start(d, minus=0):
    y, m = d.year, d.month - minus
    while m <= 0: y, m = y - 1, m + 12
    return datetime.date(y, m, 1)
CUT6, CUT12 = month_start(TODAY, 6), month_start(TODAY, 12)

b_recent = [n for n in notes if n[0] >= CUT6]
b_half   = [n for n in notes if CUT12 <= n[0] < CUT6]
b_old    = [n for n in notes if n[0] < CUT12]

def month_groups(items):
    g = collections.defaultdict(list)
    for d, f in items: g[d.strftime("%Y-%m")].append((d, f))
    return dict(sorted(g.items(), reverse=True))

def folder_groups(items):
    g = collections.defaultdict(list)
    for d, f in items: g[os.path.dirname(f) or "根目录"].append((d, f))
    for k in g: g[k].sort(key=lambda x: (-x[0].toordinal(), x[1]))
    return sorted(g.items(), key=lambda kv: (-len(kv[1]), kv[0]))

def ym_label(ym):
    y, m = ym.split("-")
    return "%s 年 %d 月" % (y, int(m))

def render_month(ym, items, expanded=False):
    lines = ["> [!note]%s %s · %d 篇" % ("" if expanded else "-", ym_label(ym), len(items))]
    for folder, its in folder_groups(items):
        lines.append("> **%s（%d 篇）**" % (folder.replace("/", " / "), len(its)))
        lines += ["> - [[%s]]" % base(f) for d, f in its]
        lines.append(">")
    if lines[-1] == ">": lines.pop()
    return "### %s · %d 篇\n\n%s\n" % (ym_label(ym), len(items), "\n".join(lines))

CURATED = [
 ("00_系统/工作台", "🌌 工作台", "快捷入口 / 待办 / 最近收录 / 热力图"),
 ("README", "🏠 首页", "全库分类入口"),
 ("00_Inbox/Inbox收件箱", "📥 Inbox 收件箱", "新素材先丢这里，每周消化"),
 ("AI大模型/AI大模型-MOC", "🤖 AI 大模型 MOC", "RAG / Agent / 训练推理 / 面试总入口"),
 ("工作/面试收集/00_题库/05-AI&大模型", "📚 面试题库 · AI&大模型", "面试主战场，题目全局编号"),
 ("工作/面试收集/面试收集-MOC", "🎯 面试收集 MOC", "题库 / 项目深挖 / 专题 / 实务 + 考前速查"),
 ("AI大模型/Agent/Agent演进全过程-Loop工程到Graph工程", "🧭 Agent 演进总纲", "五模式演进 + Workflow→ReAct→Graph"),
 ("AI大模型/Agent/生产级Agent工程架构蓝图-从Demo到千万级并发", "🏭 Agent 生产架构蓝图", "六层架构 / 状态机 / 记忆分级 / 高并发"),
 ("AI大模型/rag/RAG系统核心技术与实现", "🔍 RAG 系统实现", "检索链路核心笔记"),
 ("AI大模型/大语言模型学习/LLM与Transformer底层原理与架构演进总纲", "🧠 LLM / Transformer 总纲", "原理与架构演进"),
 ("应用&工具笔记/工具-MOC", "🛠 工具 MOC", "Clash / Docker / PowerShell / Obsidian"),
 ("工作/工作-MOC", "💼 工作 MOC", "Docker 运维、提示词、平台部署、求职"),
 ("00_系统/笔记协作手册", "📋 笔记协作手册", "人类可读版协作约定"),
]

def mdate(p):
    full = p + ".md"
    return datetime.datetime.fromtimestamp(os.stat(full).st_mtime).strftime("%Y-%m-%d") if os.path.exists(full) else "-"

MOCS = [
 ("AI/AI-MOC", "AI 认知、机器学习、强化学习、模型评估"),
 ("AIGC/AIGC-MOC", "NotebookLM、生图提示词、Coze 工作流"),
 ("AI大模型/AI大模型-MOC", "大模型 / RAG / Agent / 训练推理 / 面试"),
 ("AI大模型/LangChain/LangChain-MOC", "LangChain 1.0 与 LangGraph"),
 ("CS(计科)/CS-MOC", "数据库、开发、系统、组成原理、运维"),
 ("工作/工作-MOC", "工作场景与平台部署"),
 ("工作/面试收集/面试收集-MOC", "面试题库、项目深挖、专题研究、面试实务"),
 ("应用&工具笔记/工具-MOC", "本机与常用工具配置"),
 ("文学&认知/认知-MOC", "思维模型、金句、读书"),
 ("问题&资料收集/问题收集-MOC", "问题库（待解决 / 已解决）"),
]

L = [
"---", "title: 知识库导航页", "tags:", "  - 系统", "  - 导航", "  - 索引", "cssclasses:", "  - wide", "---", "",
"# 🧭 知识库导航页", "",
"> [!abstract] 这是什么",
"> 全库的**时间线导航**：顶部是常用入口，往下按「最近半年 → 半年～1 年 → 1 年以上」倒序，每月一组、点开即见当月收录的全部笔记。",
">",
"> **收录时间** = 该笔记在 git 仓库中**首次出现**的日期（比文件创建时间可靠，不受同步/重装影响）。",
"> **本页生成时间**：%s　·　**统计口径**：不含 `00_系统` / `00_Inbox` / `template` / `private` / `.claude`、不含各 `XX-MOC` 索引页与 `README`。" % TODAY.isoformat(),
"", "## 📊 全库速览", "",
"| 区间 | 篇数 | 说明 |", "|------|------|------|",
"| 最近半年（%s ～） | %d | 按月折叠，最新在上 |" % (CUT6.strftime("%Y-%m"), len(b_recent)),
"| 半年 ～ 1 年（%s ～ %s） | %d | 按月份组 |" % (CUT12.strftime("%Y-%m"), month_start(CUT6, 1).strftime("%Y-%m"), len(b_half)),
"| 1 年以上（～ %s） | %d | 以年为单位 |" % (month_start(CUT12, 1).strftime("%Y-%m"), len(b_old)),
"| **合计** | **%d** | — |" % len(notes),
"", "---", "", "## ⭐ 高频访问 · 精选入口", "",
"> [!tip] 用法",
"> 这里放日常最常打开的几个入口，由人工挑选维护。新增高频笔记时直接往表里加一行即可。",
"", "| 入口 | 用途 | 最近修改 |", "|------|------|----------|",
]
for p, label, desc in CURATED:
    L.append("| [[%s\\|%s]] | %s | %s |" % (p, label, desc, mdate(p)))
L += ["", "---", "", "## 🕐 最近半年收录（%s ～ %s）" % (CUT6.strftime("%Y-%m"), TODAY.strftime("%Y-%m")), "",
      "> 共 **%d 篇**，按月份倒序；每月内按主题目录分组。当前月份默认展开，其余折叠。" % len(b_recent), ""]
for ym, items in month_groups(b_recent).items():
    L += [render_month(ym, items, expanded=(ym == TODAY.strftime("%Y-%m"))), ""]
L += ["---", "", "## 📆 半年 ～ 1 年收录（%s ～ %s）" % (CUT12.strftime("%Y-%m"), month_start(CUT6, 1).strftime("%Y-%m")), "",
      "> 共 **%d 篇**。这一段是「沉淀期」笔记，回访时可当复习清单。" % len(b_half), ""]
for ym, items in month_groups(b_half).items():
    L += [render_month(ym, items), ""]
L += ["---", "", "## 🗄 一年以上收录（～ %s）" % month_start(CUT12, 1).strftime("%Y-%m"), "",
      "> 共 **%d 篇**，最早的笔记。数量少，以年为单位列出。" % len(b_old), ""]
yg = collections.defaultdict(list)
for d, f in b_old: yg[str(d.year)].append((d, f))
for y in sorted(yg, reverse=True):
    its = yg[y]
    L += ["### %s 年 · %d 篇" % (y, len(its)), ""]
    for d, f in sorted(its):
        L.append("- [[%s]] — `%s` · %s" % (base(f), d.isoformat(), os.path.dirname(f).replace("/", " / ")))
    L.append("")
L += ["---", "", "## 🧭 主题 MOC 入口", "", "| 主题 | 覆盖范围 |", "|------|----------|"]
for p, desc in MOCS:
    L.append("| [[%s\\|%s]] | %s |" % (p, os.path.basename(p), desc))
L += [
"", "---", "", "## 🔧 本页维护说明", "",
"> [!warning] 什么时候需要更新",
"> 1. **有新增笔记**：运行 `python \"00_系统/脚本/生成知识库导航页.py\"` 重新生成；或手工在对应月份的折叠块补一行链接并改篇数。",
"> 2. **高频入口变动**：直接改顶部表格，增删行即可。",
"> 3. **每月初**：跨月后重新运行脚本，「最近半年」边界会自动顺延，无需手工搬移。",
"",
"> [!note] 为什么不完全用 dataview 自动生成？",
"> Dataview 只能读 `file.ctime`（文件创建时间），在本库实测存在偏差（同步/重装后会被重置）；而「收录时间」用 git 首次入库日期更忠实。因此本页是**静态快照 + 脚本重新生成**。",
"", "## 🔄 相关入口", "",
"- [[00_系统/工作台|🌌 工作台]]", "- [[README|🏠 返回首页]]", "- [[00_系统/笔记协作手册|📋 笔记协作手册]]",
]

text = "\n".join(L) + "\n"
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
print("已生成 %s：%d 篇笔记，%d 行" % (OUT, len(notes), text.count("\n") + 1))
