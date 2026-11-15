/*
 * Workbench Sync
 * 在笔记「实质内容」变化后，自动重新生成：
 *   00_系统/知识库导航页.md
 *   00_系统/工作台-玻璃展厅.html
 * 并刷新 Dataview 视图（静态工作台 / 交互工作台）。
 *
 * 触发策略（B + C）：
 *   - 去抖：停止编辑 8 秒后检查
 *   - 最低间隔：两次自动同步至少间隔 5 分钟（可调）
 *   - 手动「立即同步」不受最低间隔限制
 *   - 只改空格/空行/光标位置不触发；Inbox 的变化不触发
 *   - 整理时把笔记从 Inbox 移到主题目录，才触发一次
 */

const { Plugin, Notice, PluginSettingTab, Setting, TFile } = require("obsidian");
const { execFile } = require("child_process");
const crypto = require("crypto");

const STATE_FILE = ".obsidian/workbench-sync-state.json";

const IGNORE_PREFIXES = [
  "00_系统/",
  "00_Inbox/",
  "00_附件/",
  "template/",
  ".obsidian/",
  ".claude/",
  "images/",
  "Excalidraw/",
  "Clippings/",
  "归档/",
  "private/",
];

const GENERATED = [
  "00_系统/知识库导航页.md",
  "00_系统/工作台-玻璃展厅.html",
];

const DEFAULT_SETTINGS = {
  enabled: true,
  debounceMs: 8000,
  minIntervalMs: 300000,
  pythonPath: "python",
  notify: true,
  runWhenClosedChanges: true,
  lastSyncAt: 0,
  pendingSync: false,
};

class WorkbenchSyncPlugin extends Plugin {
  async onload() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    this.state = await this.loadState();
    this.timer = null;
    this.trailingTimer = null;
    this.pendingSync = false;
    this.running = false;
    this.dirty = new Set();

    this.registerEvent(this.app.vault.on("modify", (f) => this.queueFile(f)));
    this.registerEvent(this.app.vault.on("create", (f) => this.queueFile(f)));
    this.registerEvent(this.app.vault.on("delete", (f) => this.queuePath(f.path)));
    this.registerEvent(
      this.app.vault.on("rename", (f, oldPath) => {
        this.queuePath(oldPath);
        this.queueFile(f);
      })
    );

    this.addSettingTab(new WorkbenchSyncSettingTab(this.app, this));

    this.app.workspace.onLayoutReady(async () => {
      try {
        await this.bootstrap();
        this.resumePending();
      } catch (e) {
        console.error("workbench-sync bootstrap", e);
      }
    });
  }

  onunload() {
    if (this.timer) clearTimeout(this.timer);
    if (this.trailingTimer) clearTimeout(this.trailingTimer);
  }

  eligible(p) {
    if (!this.settings.enabled) return false;
    if (!p || typeof p !== "string") return false;
    if (!p.endsWith(".md")) return false;
    if (GENERATED.includes(p)) return false;
    if (IGNORE_PREFIXES.some((x) => p.startsWith(x))) return false;
    return true;
  }

  queueFile(file) {
    if (file instanceof TFile) this.queuePath(file.path);
  }

  queuePath(p) {
    if (!this.eligible(p)) return;
    this.dirty.add(p);
    this.scheduleFlush(this.settings.debounceMs);
  }

  scheduleFlush(ms) {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.timer = null;
      this.flush(false).catch((e) => console.error("workbench-sync flush", e));
    }, Math.max(1000, Number(ms) || 8000));
  }

  scheduleTrailing(ms) {
    if (this.trailingTimer) clearTimeout(this.trailingTimer);
    this.trailingTimer = setTimeout(() => {
      this.trailingTimer = null;
      this.flush(false).catch((e) => console.error("workbench-sync trailing flush", e));
    }, Math.max(1000, Number(ms) || 1000));
  }

  resumePending() {
    if (!this.settings.pendingSync) return;
    this.pendingSync = true;
    const min = Math.max(0, Number(this.settings.minIntervalMs) || 0);
    const last = Number(this.settings.lastSyncAt) || 0;
    const now = Date.now();
    if (min > 0 && last > 0 && now - last < min) {
      this.scheduleTrailing(last + min - now);
    } else {
      this.scheduleFlush(1500);
    }
  }

  async bootstrap() {
    if (!this.settings.enabled) return;

    const files = this.app.vault.getMarkdownFiles().filter((f) => this.eligible(f.path));
    const next = {};
    let changed = false;

    for (const f of files) {
      const h = await this.hashPath(f.path);
      if (!h) continue;
      next[f.path] = h;
      if (this.state[f.path] !== h) changed = true;
    }
    for (const key of Object.keys(this.state)) {
      if (!(key in next)) {
        changed = true;
        break;
      }
    }

    this.state = next;
    await this.saveState();

    if (changed && this.settings.runWhenClosedChanges) {
      this.settings.pendingSync = true;
      await this.saveData(this.settings);
      this.dirty.add("__bootstrap__");
      this.scheduleFlush(2500);
    }
  }

  async hashPath(p) {
    try {
      const raw = await this.app.vault.adapter.read(p);
      // 去掉所有空白：只改空格/缩进/空行不触发
      const normalized = String(raw).replace(/\s+/g, "");
      return crypto.createHash("sha256").update(normalized).digest("hex");
    } catch (e) {
      return null;
    }
  }

  async flush(force) {
    if (this.running) {
      this.pendingSync = true;
      return;
    }
    this.running = true;
    try {
      let substantive = !!force || this.pendingSync || !!this.settings.pendingSync;
      this.pendingSync = false;

      for (const p of Array.from(this.dirty)) {
        if (p === "__bootstrap__") {
          substantive = true;
          continue;
        }
        const h = await this.hashPath(p);
        if (!h) {
          if (this.state[p]) {
            delete this.state[p];
            substantive = true;
          }
          continue;
        }
        if (this.state[p] !== h) {
          this.state[p] = h;
          substantive = true;
        }
      }
      this.dirty.clear();
      await this.saveState();

      if (!substantive) return;

      const min = Math.max(0, Number(this.settings.minIntervalMs) || 0);
      const last = Number(this.settings.lastSyncAt) || 0;
      const now = Date.now();

      // 最低间隔：到点前先不跑，留一个尾随任务，保证最终会跑
      if (!force && min > 0 && last > 0 && now - last < min) {
        this.pendingSync = true;
        this.settings.pendingSync = true;
        await this.saveData(this.settings);
        this.scheduleTrailing(last + min - now);
        return;
      }

      const ok = await this.runGenerators();
      if (ok) {
        this.pendingSync = false;
        this.settings.pendingSync = false;
        this.settings.lastSyncAt = Date.now();
        await this.saveData(this.settings);
        this.refreshDataview();
        if (this.settings.notify) new Notice("工作台已同步更新");
      }
    } finally {
      this.running = false;
      // 如果同步期间又来了改动，补一个短延迟任务
      if (this.pendingSync && !this.timer && !this.trailingTimer) {
        this.scheduleFlush(1000);
      }
    }
  }

  runGenerators() {
    const cwd = this.app.vault.adapter.basePath;
    const py = this.settings.pythonPath || "python";
    const scripts = [
      "00_系统/脚本/生成知识库导航页.py",
      "00_系统/脚本/生成玻璃展厅.py",
    ];
    return scripts
      .reduce(
        (chain, script) =>
          chain.then(
            () =>
              new Promise((resolve) => {
                execFile(
                  py,
                  [script],
                  { cwd, timeout: 120000, windowsHide: true },
                  (err, stdout, stderr) => {
                    if (err) {
                      console.error("workbench-sync:", script, err, stderr);
                      new Notice(`${script.split("/").pop()} 生成失败，详见控制台`);
                      resolve(false);
                    } else {
                      resolve(true);
                    }
                  }
                );
              })
          ),
        Promise.resolve(true)
      )
      .then((last) => last);
  }

  refreshDataview() {
    try {
      const dv = this.app.plugins.plugins["dataview"];
      if (dv && dv.index && typeof dv.index.touch === "function") dv.index.touch();
    } catch (e) {
      console.warn("workbench-sync: dataview refresh failed", e);
    }
  }

  async loadState() {
    try {
      const raw = await this.app.vault.adapter.read(STATE_FILE);
      return JSON.parse(raw);
    } catch (e) {
      return {};
    }
  }

  async saveState() {
    try {
      await this.app.vault.adapter.write(STATE_FILE, JSON.stringify(this.state));
    } catch (e) {
      console.warn("workbench-sync: save state failed", e);
    }
  }
}

class WorkbenchSyncSettingTab extends PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display() {
    const { containerEl } = this;
    containerEl.empty();

    new Setting(containerEl)
      .setName("启用自动同步")
      .setDesc("笔记实质内容变化后，自动重新生成导航页和玻璃展厅")
      .addToggle((t) =>
        t.setValue(this.plugin.settings.enabled).onChange(async (v) => {
          this.plugin.settings.enabled = v;
          await this.plugin.saveData(this.plugin.settings);
        })
      );

    new Setting(containerEl)
      .setName("去抖时间（毫秒）")
      .setDesc("停止编辑多久后才检查；默认 8000。只改空格/空行不会触发。")
      .addText((t) =>
        t
          .setPlaceholder("8000")
          .setValue(String(this.plugin.settings.debounceMs))
          .onChange(async (v) => {
            const n = Number(v);
            if (Number.isFinite(n) && n >= 1000) {
              this.plugin.settings.debounceMs = n;
              await this.plugin.saveData(this.plugin.settings);
            }
          })
      );

    new Setting(containerEl)
      .setName("最低同步间隔（分钟）")
      .setDesc("两次自动同步至少间隔这么久；默认 5 分钟。手动「立即同步」不受限制。")
      .addText((t) =>
        t
          .setPlaceholder("5")
          .setValue(String(Math.round((Number(this.plugin.settings.minIntervalMs) || 0) / 60000)))
          .onChange(async (v) => {
            const n = Number(v);
            if (Number.isFinite(n) && n >= 0) {
              this.plugin.settings.minIntervalMs = n * 60000;
              await this.plugin.saveData(this.plugin.settings);
            }
          })
      );

    new Setting(containerEl)
      .setName("Python 路径")
      .setDesc("用于执行生成脚本的 Python 可执行文件")
      .addText((t) =>
        t
          .setPlaceholder("python")
          .setValue(this.plugin.settings.pythonPath)
          .onChange(async (v) => {
            this.plugin.settings.pythonPath = v.trim() || "python";
            await this.plugin.saveData(this.plugin.settings);
          })
      );

    new Setting(containerEl)
      .setName("同步完成后提示")
      .addToggle((t) =>
        t.setValue(this.plugin.settings.notify).onChange(async (v) => {
          this.plugin.settings.notify = v;
          await this.plugin.saveData(this.plugin.settings);
        })
      );

    new Setting(containerEl)
      .setName("启动时检查离线改动")
      .setDesc("Obsidian 关闭期间新增/修改的笔记，启动后补一次同步")
      .addToggle((t) =>
        t.setValue(this.plugin.settings.runWhenClosedChanges).onChange(async (v) => {
          this.plugin.settings.runWhenClosedChanges = v;
          await this.plugin.saveData(this.plugin.settings);
        })
      );

    const last = Number(this.plugin.settings.lastSyncAt) || 0;
    new Setting(containerEl)
      .setName("上次自动同步")
      .setDesc(last ? new Date(last).toLocaleString() : "尚未同步");

    new Setting(containerEl)
      .setName("立即同步")
      .setDesc("手动触发一次：重新生成导航页和展厅，并刷新 Dataview。不受最低间隔限制。")
      .addButton((b) =>
        b.setButtonText("立即同步").onClick(async () => {
          b.setDisabled(true);
          await this.plugin.flush(true);
          b.setDisabled(false);
          this.display();
        })
      );

    new Setting(containerEl)
      .setName("已记录笔记数")
      .setDesc(String(Object.keys(this.plugin.state || {}).length));
  }
}

module.exports = WorkbenchSyncPlugin;
