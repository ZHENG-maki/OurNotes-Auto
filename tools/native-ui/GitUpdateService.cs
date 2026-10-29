// SPDX-License-Identifier: GPL-3.0-or-later
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace MFAAvalonia.Helper;

public sealed record GitCommit(string Hash, string Date, string Author, string Subject)
{
    public string Metadata => $"{Hash}  ·  {Author}  ·  {Date}";
}

public sealed record GitUpdateReport(string Status, string Log, IReadOnlyList<GitCommit> Commits,
    string CheckedAt, bool Success);

public static class GitUpdateService
{
    private static readonly SemaphoreSlim Gate = new(1, 1);
    public static bool Enabled => File.Exists(Path.Combine(AppContext.BaseDirectory, "git-update.json"));
    public static GitUpdateReport LastReport { get; private set; } =
        new("等待检查更新", "", Array.Empty<GitCommit>(), "尚未检查", false);

    public static string RepositoryLabel
    {
        get
        {
            try
            {
                using var config = JsonDocument.Parse(File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "git-update.json")));
                var repository = config.RootElement.GetProperty("repository").GetString() ?? "OurNotes-Auto";
                return Path.GetFileName(repository.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)) + "  ·  main";
            }
            catch { return "main"; }
        }
    }

    public static GitUpdateReport Parse(string output, int exitCode)
    {
        var commits = new List<GitCommit>();
        var log = new List<string>();
        var status = exitCode == 0 ? "检查完成" : "检查失败，请查看详情";
        foreach (var line in output.Split('\n'))
        {
            var text = line.TrimEnd('\r');
            if (text.StartsWith("COMMIT\t", StringComparison.Ordinal))
            {
                var fields = text.Substring(7).Split(new[] { '\t' }, 4);
                if (fields.Length == 4)
                {
                    var date = DateTimeOffset.TryParse(fields[1], out var value)
                        ? value.ToLocalTime().ToString("yyyy-MM-dd HH:mm") : fields[1];
                    commits.Add(new GitCommit(fields[0], date, fields[2], fields[3]));
                }
            }
            else if (!string.IsNullOrWhiteSpace(text))
            {
                if (text.StartsWith("STATUS\t", StringComparison.Ordinal)) status = text.Substring(7);
                log.Add(text);
            }
        }
        return new(status, string.Join(Environment.NewLine, log.TakeLast(200)), commits,
            DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"), exitCode == 0);
    }

    // Startup runs before resource/config loading. Manual checks only sync Git;
    // deployment waits for the next start, when no view has loaded old resources.
    public static async Task<GitUpdateReport> RunAsync(bool deploy, IProgress<string>? progress = null)
    {
        await Gate.WaitAsync();
        try
        {
            var root = AppContext.BaseDirectory;
            var info = new ProcessStartInfo(Path.Combine(root, "python", "python.exe"))
            {
                WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
            };
            foreach (var arg in new[] { "-X", "utf8", Path.Combine(root, "tools", "git_update.py"), "--root", root })
                info.ArgumentList.Add(arg);
            if (!deploy) info.ArgumentList.Add("--check-only");
            using var process = new Process { StartInfo = info };
            process.Start();
            var errors = process.StandardError.ReadToEndAsync();
            var output = new StringBuilder();
            while (await process.StandardOutput.ReadLineAsync() is { } line)
            {
                output.AppendLine(line);
                if (!line.StartsWith("COMMIT\t", StringComparison.Ordinal))
                    progress?.Report(line.StartsWith("STATUS\t", StringComparison.Ordinal) ? line.Substring(7) : line);
            }
            await process.WaitForExitAsync();
            output.AppendLine(await errors);
            return LastReport = Parse(output.ToString(), process.ExitCode);
        }
        catch (Exception error)
        {
            return LastReport = new("更新未完成，继续使用当前版本", error.Message,
                LastReport.Commits, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"), false);
        }
        finally { Gate.Release(); }
    }
}
