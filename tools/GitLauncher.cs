// OurNotes-Auto 修改版启动界面：保留原 MFAA 窗口，添加 Git 更新页。
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

class GitLauncher : Form {
    [DllImport("user32.dll")] static extern IntPtr SetParent(IntPtr child, IntPtr parent);
    [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr hwnd, int index);
    [DllImport("user32.dll")] static extern int SetWindowLong(IntPtr hwnd, int index, int value);
    [DllImport("user32.dll")] static extern bool MoveWindow(IntPtr hwnd, int x, int y, int w, int h, bool repaint);
    readonly string root = AppDomain.CurrentDomain.BaseDirectory;
    readonly TabControl tabs = new TabControl { Dock = DockStyle.Fill };
    readonly Panel host = new Panel { Dock = DockStyle.Fill };
    readonly Label status = new Label { Dock = DockStyle.Top, Height = 36, Text = "正在检查 Git 更新…", AutoEllipsis = true };
    readonly TextBox log = new TextBox { Dock = DockStyle.Bottom, Height = 180, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical };
    readonly DataGridView history = new DataGridView { Dock = DockStyle.Fill, ReadOnly = true, AllowUserToAddRows = false, RowHeadersVisible = false, AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill };
    readonly Button update = new Button { Text = "检查并 rebase 更新", Width = 180 };
    Process core;
    IntPtr child = IntPtr.Zero;
    bool updating;
    readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer { Interval = 200 };

    GitLauncher() {
        Text = "OurNotes-Auto · ZHENG-maki 修改版";
        Size = new Size(1320, 940); MinimumSize = new Size(900, 650);
        Font = new Font("Microsoft YaHei UI", 10);
        var play = new TabPage("演出"); var git = new TabPage("Git更新");
        var controls = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 44 };
        var open = new Button { Text = "打开演出", Width = 130 };
        var close = new Button { Text = "关闭演出窗口", Width = 150 };
        open.Click += delegate { if (!updating) StartCore(); };
        close.Click += delegate { if (Running()) core.CloseMainWindow(); };
        controls.Controls.Add(open); controls.Controls.Add(close);
        play.Controls.Add(host); play.Controls.Add(controls);
        history.Columns.Add("sha", "提交"); history.Columns.Add("date", "时间");
        history.Columns.Add("author", "作者"); history.Columns.Add("subject", "提交说明");
        history.Columns[0].FillWeight = 45; history.Columns[3].FillWeight = 230;
        var actions = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 44 };
        actions.Controls.Add(update);
        git.Controls.Add(history); git.Controls.Add(log); git.Controls.Add(actions); git.Controls.Add(status);
        tabs.TabPages.Add(play); tabs.TabPages.Add(git); Controls.Add(tabs);
        update.Click += delegate { BeginUpdate(false); };
        host.Resize += delegate { ResizeCore(); };
        tabs.SelectedIndexChanged += delegate { ResizeCore(); };
        timer.Tick += delegate {
            if (Running() && child == IntPtr.Zero) {
                core.Refresh(); var hwnd = core.MainWindowHandle;
                if (hwnd != IntPtr.Zero) {
                    child = hwnd; SetParent(child, host.Handle);
                    int style = GetWindowLong(child, -16);
                    SetWindowLong(child, -16, (style & ~0x00CF0000 & unchecked((int)~0x80000000)) | 0x40000000);
                    ResizeCore();
                }
            } else if (!Running()) child = IntPtr.Zero;
        };
        timer.Start();
        Shown += delegate { BeginUpdate(true); };
        FormClosing += delegate(object sender, FormClosingEventArgs e) {
            if (updating) { e.Cancel = true; status.Text = "更新正在进行，请等待结束后关闭"; return; }
            if (Running()) {
                core.CloseMainWindow();
                if (!core.WaitForExit(1000)) { e.Cancel = true; MessageBox.Show("请先停止演出任务并关闭演出窗口。"); }
            }
        };
    }
    bool Running() { return core != null && !core.HasExited; }
    void ResizeCore() { if (child != IntPtr.Zero) MoveWindow(child, 0, 0, host.ClientSize.Width, host.ClientSize.Height, true); }
    void StartCore() {
        if (Running()) return;
        string exe = Path.Combine(root, "MFAAvalonia.Core.exe");
        if (!File.Exists(exe)) { status.Text = "缺少原始 MFAAvalonia.Core.exe"; tabs.SelectedIndex = 1; return; }
        core = Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = root, UseShellExecute = false });
        child = IntPtr.Zero;
    }
    void Line(string line) {
        if (line == null || IsDisposed) return;
        BeginInvoke((Action)delegate {
            if (line.StartsWith("COMMIT\t")) {
                var values = line.Substring(7).Split(new char[] {'\t'}, 4);
                if (values.Length == 4) history.Rows.Add(values);
            } else {
                if (line.StartsWith("STATUS\t")) status.Text = line.Substring(7);
                log.AppendText(line + Environment.NewLine);
            }
        });
    }
    void BeginUpdate(bool launchAfter) {
        if (updating) return;
        if (Running()) { status.Text = "请先在演出页关闭演出窗口，再更新；正在运行时不替换文件。"; return; }
        updating = true; update.Enabled = false; history.Rows.Clear(); log.Clear(); status.Text = "正在 fetch / rebase origin/main…";
        new Thread(delegate() {
            int code = 1;
            try {
                var info = new ProcessStartInfo(Path.Combine(root, "python", "python.exe"),
                    "-X utf8 \"" + Path.Combine(root, "tools", "git_update.py") + "\" --root \"" + root.TrimEnd('\\') + "\"") {
                    WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                    RedirectStandardOutput = true, RedirectStandardError = true,
                    StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
                };
                using (var process = new Process { StartInfo = info }) {
                    process.OutputDataReceived += (s, e) => Line(e.Data);
                    process.ErrorDataReceived += (s, e) => Line(e.Data);
                    process.Start(); process.BeginOutputReadLine(); process.BeginErrorReadLine(); process.WaitForExit(); code = process.ExitCode;
                }
            } catch (Exception error) { Line("STATUS\t" + error.Message); }
            BeginInvoke((Action)delegate {
                updating = false; update.Enabled = true;
                if (code != 0) tabs.SelectedIndex = 1;
                if (launchAfter) StartCore();
            });
        }) { IsBackground = true }.Start();
    }
    [STAThread] static void Main() {
        bool first;
        using (var mutex = new Mutex(true, "OurNotesAutoGitLauncher", out first)) {
            if (!first) { MessageBox.Show("OurNotes-Auto 已打开。"); return; }
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false); Application.Run(new GitLauncher());
        }
    }
}
