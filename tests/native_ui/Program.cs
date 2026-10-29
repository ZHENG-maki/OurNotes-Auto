// Render actual compiled AXAML in a headless test process; no desktop input.
using Avalonia;
using Avalonia.Controls;
using Avalonia.Headless;
using Avalonia.Media;
using Avalonia.Styling;
using Avalonia.Themes.Fluent;
using Avalonia.Threading;
using Avalonia.VisualTree;
using MFAAvalonia.Helper;
using MFAAvalonia.Views.Pages;
using SukiUI;
using SukiUI.Controls;

static class Program
{
    [STAThread]
    static void Main(string[] args)
    {
        var report = GitUpdateService.Parse("正在检查 origin/main…\nSTATUS\t更新成功 · main · 022629f\n"
            + "COMMIT\t022629f\t2026-10-29T09:20:00+08:00\tZHENG-maki\t集成 Git 更新与提交记录\n"
            + "COMMIT\t85955b9\t2026-10-28T21:00:00+08:00\tZHENG-maki\t自动演出：通过列表选择歌曲\n"
            + "COMMIT\tdb9e3f2\t2026-10-28T20:30:00+08:00\tZHENG-maki\t等待歌曲开始，按谱面完成演奏\n", 0);
        if (!report.Success || report.Commits.Count != 3 || report.Commits[0].Author != "ZHENG-maki")
            throw new Exception("Commit/status parser failed");
        if (GitUpdateService.Parse("STATUS\t网络失败\nCOMMIT\tbad\n", 1).Success)
            throw new Exception("Error state parser failed");
        typeof(GitUpdateService).GetProperty(nameof(GitUpdateService.LastReport))!.SetValue(null, report);
        var configPath = Path.Combine(AppContext.BaseDirectory, "git-update.json");
        File.WriteAllText(configPath, "{\"repository\":\"OurNotes-Auto\"}");
        AppBuilder.Configure<PreviewApp>()
            .UseHeadless(new AvaloniaHeadlessPlatformOptions { UseHeadlessDrawing = false })
            .UseSkia().SetupWithoutStarting();
        var output = args.Length > 0 ? args[0] : Path.GetTempPath();
        Directory.CreateDirectory(output);
        foreach (var (name, width, height, theme) in new[] {
            ("light", 1050, 780, ThemeVariant.Light),
            ("dark", 1050, 780, ThemeVariant.Dark),
            ("compact", 700, 520, ThemeVariant.Light)
        })
        {
            Application.Current!.RequestedThemeVariant = theme;
            var page = new GitUpdateView();
            var menu = new SukiSideMenu { IsMenuExpanded = false, IsSearchEnabled = false };
            var home = new SukiSideMenuItem { Header = "首页", Icon = new TextBlock { Text = "⌂" }, PageContent = new TextBlock { Text = "首页" } };
            var git = new SukiSideMenuItem { Header = "Git更新", Icon = new TextBlock { Text = "↻" }, PageContent = page };
            menu.Items.Add(home); menu.Items.Add(git); menu.SelectedItem = git;
            var window = new Window { Width = width, Height = height, Content = menu, FontFamily = new FontFamily("Microsoft YaHei UI"), Background =
                new SolidColorBrush(theme == ThemeVariant.Dark ? Color.Parse("#191d24") : Color.Parse("#f3f6fa")) };
            window.Show();
            menu.SelectedItem = git;
            window.UpdateLayout();
            Dispatcher.UIThread.RunJobs();
            AvaloniaHeadlessPlatform.ForceRenderTimerTick();
            Dispatcher.UIThread.RunJobs();
            // Let SukiUI's page/theme entrance transitions reach their final frame.
            for (var tick = 0; tick < 80; tick++)
            {
                Thread.Sleep(16);
                Dispatcher.UIThread.RunJobs();
                AvaloniaHeadlessPlatform.ForceRenderTimerTick();
            }
            using var frame = window.CaptureRenderedFrame() ?? throw new Exception("Headless render failed");
            frame.Save(Path.Combine(output, "git-update-" + name + ".png"));
            if (!page.GetVisualDescendants().OfType<TextBlock>().Any(text => text.Text == report.Commits[0].Subject))
                throw new Exception("Commit bindings did not produce content: " + string.Join(" / ", page.GetVisualDescendants().OfType<TextBlock>().Select(text => text.Text)));
            window.Close();
        }
        File.Delete(configPath);
        Console.WriteLine("PASS: native Git page renders in light/dark/compact layouts; commit/status/error parsing");
    }
}

sealed class PreviewApp : Application
{
    public override void Initialize()
    {
        Styles.Add(new FluentTheme());
        Styles.Add(new SukiTheme());
        Resources["DefaultFontFamily"] = new FontFamily("Microsoft YaHei UI");
    }
}
