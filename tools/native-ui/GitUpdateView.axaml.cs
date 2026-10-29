// SPDX-License-Identifier: GPL-3.0-or-later
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using Avalonia.Controls;
using Avalonia.Interactivity;
using MFAAvalonia.Extensions.MaaFW;
using MFAAvalonia.Helper;

namespace MFAAvalonia.Views.Pages;

public partial class GitUpdateView : UserControl, INotifyPropertyChanged
{
    public new event PropertyChangedEventHandler? PropertyChanged;
    public string Repository => GitUpdateService.RepositoryLabel;
    public string Status { get; private set; } = "等待检查更新";
    public string CheckedAt { get; private set; } = "";
    public string Details { get; private set; } = "";
    public IReadOnlyList<GitCommit> Commits { get; private set; } = Array.Empty<GitCommit>();
    public bool IsBusy { get; private set; }
    public bool CanCheck => !IsBusy && GitUpdateService.Enabled;

    public GitUpdateView()
    {
        InitializeComponent();
        DataContext = this;
        ShowReport(GitUpdateService.LastReport);
    }

    private void Refresh() => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(null));
    private void ShowReport(GitUpdateReport report)
    {
        Status = report.Status;
        CheckedAt = "上次检查  " + report.CheckedAt;
        Details = report.Log;
        Commits = report.Commits;
        Refresh();
    }

    private async void CheckUpdate(object? sender, RoutedEventArgs args)
    {
        if (!CanCheck) return;
        if (MaaProcessor.Processors.Any(processor => processor.IsTaskRunActive || processor.TaskQueue.Count > 0))
        {
            Status = "任务正在运行，请结束后再检查更新";
            Refresh();
            return;
        }
        IsBusy = true;
        Status = "正在检查远端 main…";
        Refresh();
        try
        {
            ShowReport(await GitUpdateService.RunAsync(false, new Progress<string>(line =>
            {
                Status = line;
                Refresh();
            })));
        }
        finally { IsBusy = false; Refresh(); }
    }
}
