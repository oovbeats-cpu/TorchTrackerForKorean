using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace TorchTrackerSetup;

static class Program
{
    [STAThread]
    static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new SetupForm());
    }
}

public class SetupForm : Form
{
    private TextBox _pathTextBox;
    private Button _browseButton;
    private Button _extractButton;
    private ProgressBar _progressBar;
    private Label _statusLabel;
    private CheckBox _desktopShortcutCheckBox;
    private CheckBox _deleteSelfCheckBox;
    private Panel _completionPanel;
    private Label _completionLabel;
    private Button _openFolderButton;
    private Button _closeButton;
    private Button _closeWindowButton;

    private string _extractPath;
    private bool _extractionComplete = false;
    private bool _hasEmbeddedZip = false;
    private bool _dragging = false;
    private System.Drawing.Point _dragStart;

    private const string AppName = "TorchTracker";
    private const string EmbeddedZipName = "TorchTracker.zip";

    public SetupForm()
    {
        InitializeComponent();
        SetDefaultPath();
        CheckEmbeddedResource();
    }

    private void InitializeComponent()
    {
        this.Text = "TorchTracker Setup";
        this.Size = new System.Drawing.Size(500, 320);
        this.FormBorderStyle = FormBorderStyle.None;
        this.StartPosition = FormStartPosition.CenterScreen;
        this.BackColor = System.Drawing.Color.FromArgb(30, 30, 35);
        this.ForeColor = System.Drawing.Color.White;

        this.MouseDown += Form_MouseDown;
        this.MouseMove += Form_MouseMove;
        this.MouseUp += Form_MouseUp;

        _closeWindowButton = new Button
        {
            Text = "✕",
            Font = new System.Drawing.Font("Segoe UI", 10, System.Drawing.FontStyle.Bold),
            Location = new System.Drawing.Point(465, 5),
            Size = new System.Drawing.Size(30, 25),
            FlatStyle = FlatStyle.Flat,
            ForeColor = System.Drawing.Color.White,
            BackColor = System.Drawing.Color.Transparent,
            Cursor = Cursors.Hand
        };
        _closeWindowButton.FlatAppearance.BorderSize = 0;
        _closeWindowButton.FlatAppearance.MouseOverBackColor = System.Drawing.Color.FromArgb(200, 50, 50);
        _closeWindowButton.Click += (s, e) => Application.Exit();
        this.Controls.Add(_closeWindowButton);

        var titleLabel = new Label
        {
            Text = "TorchTracker - 토치라이트 인피니트 트래커",
            Font = new System.Drawing.Font("Segoe UI", 12, System.Drawing.FontStyle.Bold),
            ForeColor = System.Drawing.Color.White,
            Location = new System.Drawing.Point(20, 15),
            AutoSize = true
        };
        this.Controls.Add(titleLabel);

        var subtitleLabel = new Label
        {
            Text = "Portable extractor - no installation required",
            ForeColor = System.Drawing.Color.Gray,
            Location = new System.Drawing.Point(20, 42),
            AutoSize = true
        };
        this.Controls.Add(subtitleLabel);

        var pathLabel = new Label
        {
            Text = "Extract to:",
            ForeColor = System.Drawing.Color.White,
            Location = new System.Drawing.Point(20, 80),
            AutoSize = true
        };
        this.Controls.Add(pathLabel);

        _pathTextBox = new TextBox
        {
            Location = new System.Drawing.Point(20, 100),
            Size = new System.Drawing.Size(350, 23),
            BackColor = System.Drawing.Color.FromArgb(50, 50, 55),
            ForeColor = System.Drawing.Color.White,
            BorderStyle = BorderStyle.FixedSingle
        };
        this.Controls.Add(_pathTextBox);

        _browseButton = new Button
        {
            Text = "Browse...",
            Location = new System.Drawing.Point(380, 99),
            Size = new System.Drawing.Size(80, 25),
            FlatStyle = FlatStyle.Flat,
            BackColor = System.Drawing.Color.FromArgb(60, 60, 65),
            ForeColor = System.Drawing.Color.White
        };
        _browseButton.FlatAppearance.BorderColor = System.Drawing.Color.FromArgb(80, 80, 85);
        _browseButton.Click += BrowseButton_Click;
        this.Controls.Add(_browseButton);

        _desktopShortcutCheckBox = new CheckBox
        {
            Text = "Create desktop shortcut",
            ForeColor = System.Drawing.Color.White,
            Location = new System.Drawing.Point(20, 135),
            AutoSize = true
        };
        this.Controls.Add(_desktopShortcutCheckBox);

        _progressBar = new ProgressBar
        {
            Location = new System.Drawing.Point(20, 175),
            Size = new System.Drawing.Size(440, 23),
            Style = ProgressBarStyle.Continuous
        };
        this.Controls.Add(_progressBar);

        _statusLabel = new Label
        {
            Text = "Ready to extract",
            ForeColor = System.Drawing.Color.LightGray,
            Location = new System.Drawing.Point(20, 205),
            Size = new System.Drawing.Size(440, 20)
        };
        this.Controls.Add(_statusLabel);

        _extractButton = new Button
        {
            Text = "Extract",
            Location = new System.Drawing.Point(190, 235),
            Size = new System.Drawing.Size(100, 30),
            FlatStyle = FlatStyle.Flat,
            BackColor = System.Drawing.Color.FromArgb(70, 130, 180),
            ForeColor = System.Drawing.Color.White
        };
        _extractButton.FlatAppearance.BorderSize = 0;
        _extractButton.Click += ExtractButton_Click;
        this.Controls.Add(_extractButton);

        _completionPanel = new Panel
        {
            Location = new System.Drawing.Point(20, 70),
            Size = new System.Drawing.Size(440, 160),
            Visible = false,
            BackColor = System.Drawing.Color.FromArgb(30, 30, 35)
        };

        _completionLabel = new Label
        {
            Text = "Extraction complete!",
            Font = new System.Drawing.Font("Segoe UI", 11, System.Drawing.FontStyle.Bold),
            ForeColor = System.Drawing.Color.FromArgb(100, 200, 100),
            Location = new System.Drawing.Point(0, 0),
            AutoSize = true
        };
        _completionPanel.Controls.Add(_completionLabel);

        var instructionLabel = new Label
        {
            Text = "TorchTracker has been extracted.\nOpen the folder below and run TorchTracker.exe",
            ForeColor = System.Drawing.Color.White,
            Location = new System.Drawing.Point(0, 30),
            AutoSize = true
        };
        _completionPanel.Controls.Add(instructionLabel);

        var runtimeLabel = new LinkLabel
        {
            Text = "If the app opens in browser, install .NET 8 Desktop Runtime",
            Location = new System.Drawing.Point(0, 58),
            AutoSize = true,
            LinkColor = System.Drawing.Color.FromArgb(100, 180, 255)
        };
        runtimeLabel.Click += (s, e) => {
            try { Process.Start(new ProcessStartInfo("https://dotnet.microsoft.com/download/dotnet/8.0") { UseShellExecute = true }); } catch { }
        };
        _completionPanel.Controls.Add(runtimeLabel);

        var pathDisplayLabel = new Label
        {
            Name = "pathDisplayLabel",
            Location = new System.Drawing.Point(0, 75),
            AutoSize = true,
            ForeColor = System.Drawing.Color.LightGray,
            Font = new System.Drawing.Font("Consolas", 9)
        };
        _completionPanel.Controls.Add(pathDisplayLabel);

        _deleteSelfCheckBox = new CheckBox
        {
            Text = "Delete this setup file (no longer needed)",
            ForeColor = System.Drawing.Color.White,
            Location = new System.Drawing.Point(0, 105),
            AutoSize = true
        };
        _completionPanel.Controls.Add(_deleteSelfCheckBox);

        _openFolderButton = new Button
        {
            Text = "Open Folder",
            Location = new System.Drawing.Point(80, 135),
            Size = new System.Drawing.Size(100, 28),
            FlatStyle = FlatStyle.Flat,
            BackColor = System.Drawing.Color.FromArgb(70, 130, 180),
            ForeColor = System.Drawing.Color.White
        };
        _openFolderButton.FlatAppearance.BorderSize = 0;
        _openFolderButton.Click += OpenFolderButton_Click;
        _completionPanel.Controls.Add(_openFolderButton);

        _closeButton = new Button
        {
            Text = "Close",
            Location = new System.Drawing.Point(200, 135),
            Size = new System.Drawing.Size(100, 28),
            FlatStyle = FlatStyle.Flat,
            BackColor = System.Drawing.Color.FromArgb(60, 60, 65),
            ForeColor = System.Drawing.Color.White
        };
        _closeButton.FlatAppearance.BorderColor = System.Drawing.Color.FromArgb(80, 80, 85);
        _closeButton.Click += CloseButton_Click;
        _completionPanel.Controls.Add(_closeButton);

        this.Controls.Add(_completionPanel);
    }

    private void Form_MouseDown(object? sender, MouseEventArgs e)
    {
        if (e.Button == MouseButtons.Left)
        {
            _dragging = true;
            _dragStart = new System.Drawing.Point(e.X, e.Y);
        }
    }

    private void Form_MouseMove(object? sender, MouseEventArgs e)
    {
        if (_dragging)
        {
            this.Left = this.Left + e.X - _dragStart.X;
            this.Top = this.Top + e.Y - _dragStart.Y;
        }
    }

    private void Form_MouseUp(object? sender, MouseEventArgs e)
    {
        _dragging = false;
    }

    private void SetDefaultPath()
    {
        string exePath = Application.ExecutablePath;
        string exeDir = Path.GetDirectoryName(exePath) ?? "";

        if (exeDir.Contains("Downloads", StringComparison.OrdinalIgnoreCase) ||
            exeDir.Contains("Temp", StringComparison.OrdinalIgnoreCase))
        {
            _pathTextBox.Text = @"C:\TorchTracker";
        }
        else
        {
            _pathTextBox.Text = Path.Combine(exeDir, "TorchTracker");
        }
    }

    private void CheckEmbeddedResource()
    {
        var assembly = Assembly.GetExecutingAssembly();
        var resourceNames = assembly.GetManifestResourceNames();
        
        foreach (var name in resourceNames)
        {
            if (name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) ||
                name.Equals(EmbeddedZipName, StringComparison.OrdinalIgnoreCase))
            {
                _hasEmbeddedZip = true;
                _statusLabel.Text = "Ready to extract TorchTracker";
                return;
            }
        }

        _statusLabel.Text = "Error: Embedded ZIP not found in installer";
        _statusLabel.ForeColor = System.Drawing.Color.Red;
        _extractButton.Enabled = false;
    }

    private Stream? GetEmbeddedZipStream()
    {
        var assembly = Assembly.GetExecutingAssembly();
        
        var stream = assembly.GetManifestResourceStream(EmbeddedZipName);
        if (stream != null) return stream;

        foreach (var name in assembly.GetManifestResourceNames())
        {
            if (name.EndsWith(".zip", StringComparison.OrdinalIgnoreCase))
            {
                return assembly.GetManifestResourceStream(name);
            }
        }
        
        return null;
    }

    private void BrowseButton_Click(object? sender, EventArgs e)
    {
        using var dialog = new FolderBrowserDialog
        {
            Description = "Select extraction folder",
            UseDescriptionForTitle = true,
            SelectedPath = _pathTextBox.Text
        };

        if (dialog.ShowDialog() == DialogResult.OK)
        {
            _pathTextBox.Text = dialog.SelectedPath;
        }
    }

    private async void ExtractButton_Click(object? sender, EventArgs e)
    {
        if (!_hasEmbeddedZip)
        {
            MessageBox.Show("Embedded ZIP not found in installer.",
                "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return;
        }

        _extractPath = _pathTextBox.Text;

        if (string.IsNullOrWhiteSpace(_extractPath))
        {
            MessageBox.Show("Please select an extraction path.", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return;
        }

        _extractButton.Enabled = false;
        _browseButton.Enabled = false;
        _pathTextBox.Enabled = false;
        _desktopShortcutCheckBox.Enabled = false;

        try
        {
            await Task.Run(() => ExtractEmbeddedZip());

            if (_desktopShortcutCheckBox.Checked)
            {
                CreateDesktopShortcut();
            }

            ShowCompletionPanel();
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Extraction failed: {ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);

            _extractButton.Enabled = true;
            _browseButton.Enabled = true;
            _pathTextBox.Enabled = true;
            _desktopShortcutCheckBox.Enabled = true;
            _statusLabel.Text = "Extraction failed. Please try again.";
        }
    }

    private void ExtractEmbeddedZip()
    {
        this.Invoke((Action)(() => {
            _statusLabel.Text = "Extracting...";
            _progressBar.Value = 0;
        }));

        Directory.CreateDirectory(_extractPath);

        using var zipStream = GetEmbeddedZipStream();
        if (zipStream == null)
        {
            throw new Exception("Could not read embedded ZIP resource");
        }

        using var archive = new ZipArchive(zipStream, ZipArchiveMode.Read);
        var totalEntries = archive.Entries.Count;
        var extractedEntries = 0;

        foreach (var entry in archive.Entries)
        {
            if (string.IsNullOrEmpty(entry.Name))
            {
                extractedEntries++;
                continue;
            }

            var relativePath = entry.FullName;
            if (relativePath.StartsWith("TorchTracker/", StringComparison.OrdinalIgnoreCase))
            {
                relativePath = relativePath.Substring(13);
            }
            else if (relativePath.StartsWith("TorchTracker\\", StringComparison.OrdinalIgnoreCase))
            {
                relativePath = relativePath.Substring(13);
            }

            var destPath = Path.Combine(_extractPath, relativePath);
            var destDir = Path.GetDirectoryName(destPath);

            if (!string.IsNullOrEmpty(destDir))
            {
                Directory.CreateDirectory(destDir);
            }

            entry.ExtractToFile(destPath, overwrite: true);

            extractedEntries++;
            var progress = (extractedEntries * 100) / totalEntries;
            var currentEntry = extractedEntries;
            
            this.Invoke((Action)(() => {
                _progressBar.Value = progress;
                _statusLabel.Text = $"Extracting... {currentEntry}/{totalEntries} files";
            }));
        }

        this.Invoke((Action)(() => {
            _progressBar.Value = 100;
            _statusLabel.Text = "Extraction complete!";
        }));
        
        _extractionComplete = true;
    }

    private void CreateDesktopShortcut()
    {
        try
        {
            var desktopPath = Environment.GetFolderPath(Environment.SpecialFolder.Desktop);
            var shortcutPath = Path.Combine(desktopPath, "TorchTracker.lnk");
            var targetPath = Path.Combine(_extractPath, "TorchTracker.exe");

            var script = $@"
                $WshShell = New-Object -ComObject WScript.Shell
                $Shortcut = $WshShell.CreateShortcut('{shortcutPath}')
                $Shortcut.TargetPath = '{targetPath}'
                $Shortcut.WorkingDirectory = '{_extractPath}'
                $Shortcut.Description = 'TorchTracker - 토치라이트 인피니트 트래커'
                $Shortcut.Save()
            ";

            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = $"-NoProfile -ExecutionPolicy Bypass -Command \"{script.Replace("\"", "\\\"")}\"",
                CreateNoWindow = true,
                UseShellExecute = false
            };

            using var process = Process.Start(psi);
            process?.WaitForExit(5000);
        }
        catch
        {
        }
    }

    private void ShowCompletionPanel()
    {
        _pathTextBox.Visible = false;
        _browseButton.Visible = false;
        _progressBar.Visible = false;
        _desktopShortcutCheckBox.Visible = false;
        _extractButton.Visible = false;

        foreach (Control c in this.Controls)
        {
            if (c is Label label && label.Text == "Extract to:")
            {
                label.Visible = false;
            }
        }

        var pathLabel = _completionPanel.Controls["pathDisplayLabel"] as Label;
        if (pathLabel != null)
        {
            pathLabel.Text = _extractPath;
        }

        _statusLabel.Visible = false;
        _completionPanel.Visible = true;
    }

    private void OpenFolderButton_Click(object? sender, EventArgs e)
    {
        try
        {
            var exePath = Path.Combine(_extractPath, "TorchTracker.exe");
            if (File.Exists(exePath))
            {
                Process.Start("explorer.exe", $"/select,\"{exePath}\"");
            }
            else
            {
                Process.Start("explorer.exe", _extractPath);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Could not open folder: {ex.Message}", "Error",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private void CloseButton_Click(object? sender, EventArgs e)
    {
        if (_deleteSelfCheckBox.Checked && _extractionComplete)
        {
            try
            {
                var selfPath = Application.ExecutablePath;
                var batchPath = Path.Combine(Path.GetTempPath(), "torchtracker_cleanup.bat");

                var batchContent = $@"
@echo off
timeout /t 2 /nobreak > nul
del ""{selfPath}""
del ""{batchPath}""
";
                File.WriteAllText(batchPath, batchContent);

                var psi = new ProcessStartInfo
                {
                    FileName = batchPath,
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                Process.Start(psi);
            }
            catch
            {
            }
        }

        Application.Exit();
    }
}
