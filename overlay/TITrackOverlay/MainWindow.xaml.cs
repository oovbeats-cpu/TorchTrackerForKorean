using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Threading;

namespace TITrackOverlay
{
    public partial class MainWindow : Window
    {
        // ── P/Invoke ────────────────────────────────────────────────

        [DllImport("user32.dll")]
        static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

        [DllImport("user32.dll")]
        static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        static extern bool IsIconic(IntPtr hWnd);

        [DllImport("user32.dll")]
        static extern bool IsWindowVisible(IntPtr hWnd);

        [DllImport("user32.dll")]
        static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

        [DllImport("user32.dll")]
        static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

        [DllImport("user32.dll")]
        static extern int GetWindowLong(IntPtr hWnd, int nIndex);

        [DllImport("user32.dll")]
        static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

        [DllImport("dwmapi.dll")]
        static extern int DwmGetWindowAttribute(IntPtr hwnd, int dwAttribute, out RECT pvAttribute, int cbAttribute);

        delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

        [StructLayout(LayoutKind.Sequential)]
        public struct RECT { public int Left, Top, Right, Bottom; }

        const int WM_NCHITTEST = 0x0084;
        const int WM_MOVING = 0x0216;
        const int WM_MOUSEACTIVATE = 0x0021;
        const int HTTRANSPARENT = -1;
        const int HTCAPTION = 2;
        const int MA_NOACTIVATE = 3;
        const int GWL_EXSTYLE = -20;
        const int WS_EX_TRANSPARENT = 0x00000020;
        const int DWMWA_EXTENDED_FRAME_BOUNDS = 9;

        // ── Constants ───────────────────────────────────────────────

        const double DEFAULT_WIDTH = 940;
        const double BAR_HEIGHT = 38;
        const double LOCK_BTN_SIZE = 22;
        const int API_HEALTH_MAX_FAILURES = 15;

        static readonly string[] GameTitles =
            { "Torchlight: Infinite", "토치라이트: 인피니트" };

        // Colors
        static readonly Color ColorBg        = Color.FromRgb(18, 18, 30);
        static readonly Color ColorLabel     = Color.FromRgb(240, 240, 248);
        static readonly Color ColorValue     = Color.FromRgb(224, 224, 224);
        static readonly Color ColorProfit    = Color.FromRgb(78, 204, 163);
        static readonly Color ColorProfitNeg = Color.FromRgb(231, 76, 60);
        static readonly Color ColorContract  = Color.FromRgb(93, 173, 226);
        static readonly Color ColorAccum     = Color.FromRgb(255, 165, 50);  // Orange for totals

        // ── Column Definitions ──────────────────────────────────────

        record ColumnDef(string Label, string FullLabel, string Key, Color ValueColor);

        static readonly ColumnDef[] AllColumns =
        {
            new("",             "회차",          "run_count",    ColorValue),
            new("현재수익",      "현재 수익",      "profit",       ColorProfit),
            new("현재소요시간",   "현재 런 시간",   "run_time",     ColorValue),
            new("누적",         "누적 수익",      "total_profit", ColorAccum),
            new("총시간",       "총 시간",        "total_time",   ColorAccum),
            new("맵핑/h",       "맵핑 / h",      "map_hr",       ColorValue),
            new("총/h",         "총 / h",        "total_hr",     ColorValue),
            new("계약",         "계약",           "contract",     ColorContract),
        };

        // Row-1 keys for preset 2 (two-row mode)
        static readonly HashSet<string> Preset2Row1Keys = new()
        {
            "run_count", "profit", "run_time", "total_profit", "total_time"
        };

        // ── State ───────────────────────────────────────────────────

        readonly string _apiBase;
        bool _locked = true;
        double _scale = 1.0;
        double _overlayOpacity = 0.9;
        double _bgOpacity = 0.7;  // Background opacity in locked mode (0=transparent, 1=opaque)
        bool _textShadow = true;
        int _preset = 1;  // 1=horizontal, 2=two-row, 3=vertical-left
        bool _userVisible = true;
        bool _hasActiveRun;
        HashSet<string> _visibleColumns;
        IntPtr _gameHwnd;
        bool _overlayVisible;
        bool _gameFoundBefore;
        bool _wasShowing;
        int _consecutiveFailures;
        DateTime _lastInteraction = DateTime.MinValue;

        // Data from API
        readonly Dictionary<string, string> _data = new()
        {
            ["run_count"]    = "0회차",
            ["profit"]       = "--",
            ["run_time"]     = "--:--",
            ["total_profit"] = "--",
            ["total_time"]   = "00:00",
            ["map_hr"]       = "0",
            ["total_hr"]     = "0",
            ["contract"]     = "--",
        };
        bool _profitNegative;

        // Time interpolation (smooth 1-second display without extra API calls)
        double _apiTotalSec;       // Last API-reported total_play_seconds
        double _apiRunSec;         // Last API-reported current_map_play_seconds
        DateTime _apiTimePollAt;   // When we received the above values
        string _totalPlayState = "stopped";
        string _mappingPlayState = "stopped";

        // UI
        readonly Dictionary<string, TextBlock> _valueBlocks = new();
        readonly Dictionary<string, TextBlock> _labelBlocks = new();
        Border _bgBorder;  // Background border with rounded corners
        Grid _innerGrid;   // Replaces direct ContentGrid use for columns
        IntPtr _hwnd;
        readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(2) };

        // Lock button (separate window)
        Window? _lockWindow;
        TextBlock? _lockText;
        IntPtr _lockHwnd;

        // ── Constructor ─────────────────────────────────────────────

        public MainWindow(string host, int port)
        {
            InitializeComponent();
            _apiBase = $"http://{host}:{port}/api";
            _visibleColumns = new HashSet<string>
            {
                "run_count", "profit", "run_time", "total_profit", "total_time",
                "map_hr", "total_hr", "contract"
            };

            Width = DEFAULT_WIDTH;
            Height = BAR_HEIGHT;
            SizeToContent = SizeToContent.Width;

            RebuildLayout();
            UpdateBackground();
            CreateLockWindow();
        }

        protected override void OnSourceInitialized(EventArgs e)
        {
            base.OnSourceInitialized(e);
            _hwnd = new WindowInteropHelper(this).Handle;
            HwndSource.FromHwnd(_hwnd)?.AddHook(WndProc);

            // Start with click-through enabled
            SetClickThrough(true);

            Hide();
            StartTimers();

            // Sync lock window position when main window moves
            LocationChanged += (_, _) => SyncLockWindowPosition();
            SizeChanged += (_, _) => SyncLockWindowPosition();
        }

        // ── Click-Through ─────────────────────────────────────────

        void SetClickThrough(bool enable)
        {
            if (_hwnd == IntPtr.Zero) return;
            int exStyle = GetWindowLong(_hwnd, GWL_EXSTYLE);
            if (enable)
                SetWindowLong(_hwnd, GWL_EXSTYLE, exStyle | WS_EX_TRANSPARENT);
            else
                SetWindowLong(_hwnd, GWL_EXSTYLE, exStyle & ~WS_EX_TRANSPARENT);
        }

        // ── Lock Button Window ────────────────────────────────────

        void CreateLockWindow()
        {
            _lockText = new TextBlock
            {
                Text = "\U0001F512",
                FontSize = 10,
                Foreground = Brushes.White,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center,
            };

            _lockWindow = new Window
            {
                AllowsTransparency = true,
                WindowStyle = WindowStyle.None,
                Background = new SolidColorBrush(Color.FromArgb(38, 255, 255, 255)),
                Topmost = true,
                ShowInTaskbar = false,
                ShowActivated = false,
                ResizeMode = ResizeMode.NoResize,
                Width = LOCK_BTN_SIZE,
                Height = LOCK_BTN_SIZE,
                Content = _lockText,
            };

            _lockWindow.SourceInitialized += (_, _) =>
            {
                _lockHwnd = new WindowInteropHelper(_lockWindow).Handle;
                HwndSource.FromHwnd(_lockHwnd)?.AddHook(LockWndProc);
            };

            _lockWindow.MouseLeftButtonDown += (_, e) =>
            {
                _lastInteraction = DateTime.Now;
                if (e.ClickCount == 2)
                {
                    ToggleLock();
                    e.Handled = true;
                }
            };
        }

        void ToggleLock()
        {
            _locked = !_locked;
            SetClickThrough(_locked);
            UpdateBackground();
            if (_lockText != null)
                _lockText.Text = _locked ? "\U0001F512" : "\U0001F513";
            _ = PostConfigAsync(new Dictionary<string, object> { { "locked", _locked } });
        }

        IntPtr LockWndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            // Prevent lock button from stealing focus from game
            if (msg == WM_MOUSEACTIVATE)
            {
                handled = true;
                return new IntPtr(MA_NOACTIVATE);
            }
            return IntPtr.Zero;
        }

        void SyncLockWindowPosition()
        {
            if (_lockWindow == null) return;
            if (_preset == 3)
            {
                // Preset 3: lock at top-right corner of overlay
                _lockWindow.Left = Left + ActualWidth + 2;
                _lockWindow.Top = Top;
            }
            else
            {
                _lockWindow.Left = Left + ActualWidth + 2;
                _lockWindow.Top = Top + (BAR_HEIGHT - LOCK_BTN_SIZE) / 2;
            }
        }

        void ShowLockWindow()
        {
            if (_lockWindow != null && !_lockWindow.IsVisible)
            {
                _lockWindow.Show();
                _lockWindow.Topmost = true;
            }
        }

        void HideLockWindow()
        {
            if (_lockWindow != null && _lockWindow.IsVisible)
                _lockWindow.Hide();
        }

        // ── Layout ──────────────────────────────────────────────────

        void RebuildLayout()
        {
            ContentGrid.Children.Clear();
            _valueBlocks.Clear();
            _labelBlocks.Clear();

            var active = AllColumns
                .Where(c => _visibleColumns.Contains(c.Key)).ToList();

            switch (_preset)
            {
                case 2:
                    BuildPreset2(active);
                    break;
                case 3:
                    BuildPreset3(active);
                    break;
                default:
                    BuildPreset1(active);
                    break;
            }
        }

        // Preset 1: Horizontal single row
        void BuildPreset1(List<ColumnDef> active)
        {
            _bgBorder = new Border
            {
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(10, 4, 10, 4),
                VerticalAlignment = VerticalAlignment.Center,
            };
            _innerGrid = new Grid();

            for (int i = 0; i < active.Count; i++)
            {
                var def = active[i];
                _innerGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

                var panel = new StackPanel
                {
                    Orientation = Orientation.Horizontal,
                    VerticalAlignment = VerticalAlignment.Center,
                    HorizontalAlignment = HorizontalAlignment.Center,
                    Margin = new Thickness(6, 0, 6, 0),
                };

                if (!string.IsNullOrEmpty(def.Label))
                {
                    var label = MakeText(def.Label, 14, FontWeights.Normal, ColorLabel);
                    label.Margin = new Thickness(0, 0, 8, 0);
                    panel.Children.Add(label);
                    _labelBlocks[def.Key] = label;
                }

                var value = MakeText(_data.GetValueOrDefault(def.Key, "--"),
                    14, FontWeights.Bold,
                    (def.Key == "profit" && _profitNegative) ? ColorProfitNeg : def.ValueColor);
                panel.Children.Add(value);

                Grid.SetColumn(panel, i);
                _innerGrid.Children.Add(panel);
                _valueBlocks[def.Key] = value;
            }

            _bgBorder.Child = _innerGrid;
            ContentGrid.Children.Add(_bgBorder);
            SizeToContent = SizeToContent.Width;
            Height = BAR_HEIGHT * Math.Max(1.0, _scale);
        }

        // Preset 2: Two-row (row1=run_count~total_time, row2=rest; auto-collapse)
        void BuildPreset2(List<ColumnDef> active)
        {
            var row1 = active.Where(c => Preset2Row1Keys.Contains(c.Key)).ToList();
            var row2 = active.Where(c => !Preset2Row1Keys.Contains(c.Key)).ToList();

            // Auto-collapse to single row if row2 is empty
            if (row2.Count == 0)
            {
                BuildPreset1(active);
                return;
            }

            _bgBorder = new Border
            {
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(10, 2, 10, 2),
                VerticalAlignment = VerticalAlignment.Center,
            };

            var outerStack = new StackPanel { Orientation = Orientation.Vertical };

            void AddRow(List<ColumnDef> items)
            {
                var grid = new Grid();
                for (int i = 0; i < items.Count; i++)
                {
                    var def = items[i];
                    grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
                    var panel = new StackPanel
                    {
                        Orientation = Orientation.Horizontal,
                        VerticalAlignment = VerticalAlignment.Center,
                        HorizontalAlignment = HorizontalAlignment.Center,
                        Margin = new Thickness(6, 1, 6, 1),
                    };
                    if (!string.IsNullOrEmpty(def.Label))
                    {
                        var label = MakeText(def.Label, 13, FontWeights.Normal, ColorLabel);
                        label.Margin = new Thickness(0, 0, 6, 0);
                        panel.Children.Add(label);
                        _labelBlocks[def.Key] = label;
                    }
                    var value = MakeText(_data.GetValueOrDefault(def.Key, "--"),
                        13, FontWeights.Bold,
                        (def.Key == "profit" && _profitNegative) ? ColorProfitNeg : def.ValueColor);
                    panel.Children.Add(value);
                    Grid.SetColumn(panel, i);
                    grid.Children.Add(panel);
                    _valueBlocks[def.Key] = value;
                }
                outerStack.Children.Add(grid);
            }

            AddRow(row1);
            AddRow(row2);

            _innerGrid = new Grid();
            _bgBorder.Child = outerStack;
            ContentGrid.Children.Add(_bgBorder);
            SizeToContent = SizeToContent.Width;
            Height = (BAR_HEIGHT * 2 - 8) * Math.Max(1.0, _scale);
        }

        // Preset 3: Vertical multi-line, left-aligned
        void BuildPreset3(List<ColumnDef> active)
        {
            _bgBorder = new Border
            {
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(12, 6, 12, 6),
                VerticalAlignment = VerticalAlignment.Top,
            };

            var stack = new StackPanel { Orientation = Orientation.Vertical };

            foreach (var def in active)
            {
                var panel = new StackPanel
                {
                    Orientation = Orientation.Horizontal,
                    HorizontalAlignment = HorizontalAlignment.Left,
                    Margin = new Thickness(0, 1, 0, 1),
                };

                string lbl = string.IsNullOrEmpty(def.FullLabel) ? def.Key : def.FullLabel;
                var label = MakeText(lbl, 13, FontWeights.Normal, ColorLabel);
                label.Width = 100 * _scale;
                panel.Children.Add(label);
                _labelBlocks[def.Key] = label;

                var value = MakeText(_data.GetValueOrDefault(def.Key, "--"),
                    13, FontWeights.Bold,
                    (def.Key == "profit" && _profitNegative) ? ColorProfitNeg : def.ValueColor);
                panel.Children.Add(value);
                _valueBlocks[def.Key] = value;

                stack.Children.Add(panel);
            }

            _innerGrid = new Grid();
            _bgBorder.Child = stack;
            ContentGrid.Children.Add(_bgBorder);
            SizeToContent = SizeToContent.WidthAndHeight;
            Height = double.NaN;  // Auto height
        }

        TextBlock MakeText(string text, double baseSize, FontWeight weight, Color color)
        {
            var tb = new TextBlock
            {
                Text = text,
                FontSize = baseSize * _scale,
                FontWeight = weight,
                FontFamily = new FontFamily("Pretendard, Segoe UI, sans-serif"),
                Foreground = new SolidColorBrush(color),
                Opacity = 0.85,
                VerticalAlignment = VerticalAlignment.Center,
            };
            if (_textShadow)
            {
                tb.Effect = new DropShadowEffect
                {
                    ShadowDepth = 1,
                    Direction = 315,
                    Color = Colors.Black,
                    Opacity = 1.0,
                    BlurRadius = 0,
                };
            }
            return tb;
        }

        void UpdateBackground()
        {
            if (_bgBorder == null) return;

            if (_locked)
            {
                // Semi-transparent or fully transparent bg based on _bgOpacity
                byte alpha = (byte)(_bgOpacity * 255);
                _bgBorder.Background = alpha > 0
                    ? new SolidColorBrush(Color.FromArgb(alpha, ColorBg.R, ColorBg.G, ColorBg.B))
                    : Brushes.Transparent;
                ContentGrid.Background = Brushes.Transparent;
                Opacity = 1.0;
            }
            else
            {
                _bgBorder.Background = new SolidColorBrush(ColorBg);
                ContentGrid.Background = Brushes.Transparent;
                Opacity = _overlayOpacity;
            }
            if (_lockText != null)
                _lockText.Text = _locked ? "\U0001F512" : "\U0001F513";
        }

        void UpdateValues()
        {
            foreach (var (key, text) in _data)
            {
                if (_valueBlocks.TryGetValue(key, out var tb))
                {
                    tb.Text = text;
                    if (key == "profit")
                    {
                        var c = _profitNegative ? ColorProfitNeg : ColorProfit;
                        tb.Foreground = new SolidColorBrush(c);
                    }
                }
            }
        }

        // ── WndProc Hook ────────────────────────────────────────────

        IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam,
                       ref bool handled)
        {
            if (msg == WM_MOUSEACTIVATE)
            {
                handled = true;
                return new IntPtr(MA_NOACTIVATE);
            }

            if (msg == WM_NCHITTEST)
            {
                handled = true;
                return new IntPtr(_locked ? HTTRANSPARENT : HTCAPTION);
            }

            // Clamp overlay position to game window during drag
            if (msg == WM_MOVING && _gameHwnd != IntPtr.Zero)
            {
                if (GetGameVisibleRect(_gameHwnd, out var gameRect))
                {
                    var rect = Marshal.PtrToStructure<RECT>(lParam);
                    int ow = rect.Right - rect.Left;
                    int oh = rect.Bottom - rect.Top;

                    if (rect.Left < gameRect.Left)
                    { rect.Left = gameRect.Left; rect.Right = rect.Left + ow; }
                    if (rect.Top < gameRect.Top)
                    { rect.Top = gameRect.Top; rect.Bottom = rect.Top + oh; }
                    if (rect.Right > gameRect.Right)
                    { rect.Left = gameRect.Right - ow; rect.Right = gameRect.Right; }
                    if (rect.Bottom > gameRect.Bottom)
                    { rect.Top = gameRect.Bottom - oh; rect.Bottom = gameRect.Bottom; }

                    Marshal.StructureToPtr(rect, lParam, false);
                    handled = true;
                    return new IntPtr(1);
                }
            }

            return IntPtr.Zero;
        }

        // ── Mouse Events ────────────────────────────────────────────

        protected override void OnMouseLeftButtonDown(MouseButtonEventArgs e)
        {
            base.OnMouseLeftButtonDown(e);
            _lastInteraction = DateTime.Now;
            if (!_locked)
                DragMove();
        }

        // ── Timers ──────────────────────────────────────────────────

        void StartTimers()
        {
            var dataTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
            dataTimer.Tick += async (_, _) => await PollDataAsync();
            dataTimer.Start();

            var configTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(2) };
            configTimer.Tick += async (_, _) => await PollConfigAsync();
            configTimer.Start();

            var gameTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
            gameTimer.Tick += (_, _) => MonitorGameWindow();
            gameTimer.Start();

            // 1-second display timer for smooth time interpolation
            var displayTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
            displayTimer.Tick += (_, _) => InterpolateTime();
            displayTimer.Start();
        }

        void InterpolateTime()
        {
            if (_apiTimePollAt == default) return;

            bool changed = false;
            double elapsed = (DateTime.Now - _apiTimePollAt).TotalSeconds;

            // Interpolate total time
            if (_totalPlayState == "playing")
            {
                double totalSec = _apiTotalSec + elapsed;
                string tt = FormatTime(totalSec);
                if (_data["total_time"] != tt) { _data["total_time"] = tt; changed = true; }
            }

            // Interpolate run time
            if (_mappingPlayState == "playing")
            {
                double runSec = _apiRunSec + elapsed;
                string rt = FormatTime(runSec);
                if (_data["run_time"] != rt) { _data["run_time"] = rt; changed = true; }
            }

            if (changed) UpdateValues();
        }

        // ── API Polling ─────────────────────────────────────────────

        async System.Threading.Tasks.Task PollDataAsync()
        {
            bool anySuccess = false;
            bool changed = false;

            // Active run → profit
            try
            {
                var doc = await GetJsonAsync($"{_apiBase}/runs/active");
                if (doc != null && doc.Value.ValueKind == JsonValueKind.Object)
                {
                    anySuccess = true;
                    _hasActiveRun = true;
                    double val = GetNum(doc, "net_value_fe")
                              ?? GetNum(doc, "total_value") ?? 0;
                    string profit = FormatFE(val);
                    bool neg = val < 0;

                    if (_data["profit"] != profit || _profitNegative != neg)
                    {
                        _data["profit"] = profit;
                        _profitNegative = neg;
                        changed = true;
                    }
                }
                else
                {
                    anySuccess = doc != null; // null JSON is still a successful response
                    _hasActiveRun = false;
                    if (_data["profit"] != "--")
                    {
                        _data["profit"] = "--";
                        _profitNegative = false;
                        changed = true;
                    }
                }
            }
            catch { _hasActiveRun = false; }

            // Time tracking
            try
            {
                var doc = await GetJsonAsync($"{_apiBase}/time");
                if (doc != null)
                {
                    anySuccess = true;
                    double runSec = GetNum(doc, "current_map_play_seconds") ?? 0;
                    double totalSec = GetNum(doc, "total_play_seconds") ?? 0;
                    string mapState = GetStr(doc, "mapping_play_state") ?? "stopped";
                    string totalState = GetStr(doc, "total_play_state") ?? "stopped";
                    string contract = GetStr(doc, "contract_setting") ?? "--";

                    // Store for interpolation
                    _apiTotalSec = totalSec;
                    _apiRunSec = runSec;
                    _apiTimePollAt = DateTime.Now;
                    _totalPlayState = totalState;
                    _mappingPlayState = mapState;

                    // Only update time display here when NOT playing (interpolation handles playing state)
                    if (mapState != "playing")
                    {
                        string rt = (mapState == "stopped" && runSec == 0)
                            ? "--:--" : FormatTime(runSec);
                        if (_data["run_time"] != rt) { _data["run_time"] = rt; changed = true; }
                    }
                    if (totalState != "playing")
                    {
                        string tt = FormatTime(totalSec);
                        if (_data["total_time"] != tt) { _data["total_time"] = tt; changed = true; }
                    }

                    string ct = string.IsNullOrEmpty(contract) ? "--" : contract;
                    if (_data["contract"] != ct) { _data["contract"] = ct; changed = true; }
                }
            }
            catch { }

            // Performance
            try
            {
                var doc = await GetJsonAsync($"{_apiBase}/runs/performance");
                if (doc != null)
                {
                    anySuccess = true;
                    string mh = FormatFE(GetNum(doc, "profit_per_hour_mapping") ?? 0);
                    string th = FormatFE(GetNum(doc, "profit_per_hour_total") ?? 0);
                    string tp = FormatFE(GetNum(doc, "total_net_profit_fe") ?? 0);

                    // Run count: completed + 1 if currently in a run
                    int completed = (int)(GetNum(doc, "run_count") ?? 0);
                    int current = _hasActiveRun ? completed + 1 : completed;
                    string rc = $"{current}회차";

                    if (_data["map_hr"] != mh) { _data["map_hr"] = mh; changed = true; }
                    if (_data["total_hr"] != th) { _data["total_hr"] = th; changed = true; }
                    if (_data["total_profit"] != tp) { _data["total_profit"] = tp; changed = true; }
                    if (_data["run_count"] != rc) { _data["run_count"] = rc; changed = true; }
                }
            }
            catch { }

            if (changed) UpdateValues();

            if (anySuccess)
                _consecutiveFailures = 0;
            else
            {
                _consecutiveFailures++;
                if (_consecutiveFailures >= API_HEALTH_MAX_FAILURES)
                    Application.Current.Shutdown();
            }
        }

        async System.Threading.Tasks.Task PollConfigAsync()
        {
            try
            {
                var doc = await GetJsonAsync($"{_apiBase}/overlay/config");
                if (doc == null) return;

                // Opacity
                double opacity = Math.Clamp(GetNum(doc, "opacity") ?? 0.9, 0.1, 1.0);
                if (Math.Abs(opacity - _overlayOpacity) > 0.01)
                {
                    _overlayOpacity = opacity;
                    if (!_locked) Opacity = _overlayOpacity;
                }

                // Background opacity (locked mode)
                double bgOp = Math.Clamp(GetNum(doc, "bg_opacity") ?? 0.7, 0.0, 1.0);
                if (Math.Abs(bgOp - _bgOpacity) > 0.01)
                {
                    _bgOpacity = bgOp;
                    if (_locked) UpdateBackground();
                }

                // Scale
                double scale = Math.Clamp(GetNum(doc, "scale") ?? 1.0, 0.8, 1.5);
                if (Math.Abs(scale - _scale) > 0.01)
                {
                    _scale = scale;
                    Height = BAR_HEIGHT * Math.Max(1.0, _scale);
                    RebuildLayout();
                    UpdateBackground();
                    UpdateValues();
                }

                // Visibility
                bool visible = GetBool(doc, "visible") ?? true;
                if (visible != _userVisible)
                {
                    _userVisible = visible;
                    if (!visible) { HideOverlay(); HideLockWindow(); }
                }

                // Locked state
                bool locked = GetBool(doc, "locked") ?? true;
                if (locked != _locked)
                {
                    _locked = locked;
                    SetClickThrough(_locked);
                    UpdateBackground();
                    if (_lockText != null)
                        _lockText.Text = _locked ? "\U0001F512" : "\U0001F513";
                }

                // Visible columns
                var columns = GetStrArray(doc, "visible_columns");
                if (columns != null)
                {
                    var newSet = new HashSet<string>(columns);
                    if (!newSet.SetEquals(_visibleColumns))
                    {
                        _visibleColumns = newSet;
                        RebuildLayout();
                        UpdateBackground();
                        UpdateValues();
                    }
                }

                // Text shadow
                bool shadow = GetBool(doc, "text_shadow") ?? true;
                if (shadow != _textShadow)
                {
                    _textShadow = shadow;
                    RebuildLayout();
                    UpdateBackground();
                    UpdateValues();
                }

                // Preset
                int preset = (int)(GetNum(doc, "preset") ?? 1);
                preset = Math.Clamp(preset, 1, 3);
                if (preset != _preset)
                {
                    _preset = preset;
                    RebuildLayout();
                    UpdateBackground();
                    UpdateValues();
                    PositionOverlay();
                }
            }
            catch { }
        }

        // ── Game Window Monitoring ──────────────────────────────────

        void MonitorGameWindow()
        {
            var gameHwnd = FindGameWindow();

            if (gameHwnd != IntPtr.Zero && _userVisible)
            {
                _gameHwnd = gameHwnd;

                if (!_gameFoundBefore)
                {
                    PositionOverlay();
                    _gameFoundBefore = true;
                }

                if (IsIconic(gameHwnd))
                {
                    HideOverlay();
                    HideLockWindow();
                    _wasShowing = false;
                }
                else
                {
                    var fg = GetForegroundWindow();
                    bool recentInteraction = (DateTime.Now - _lastInteraction).TotalSeconds < 2;
                    if (fg == gameHwnd || fg == _hwnd || fg == _lockHwnd || recentInteraction)
                    {
                        ShowOverlay();
                        ShowLockWindow();
                        SyncLockWindowPosition();
                        _wasShowing = true;
                    }
                    else
                    {
                        HideOverlay();
                        HideLockWindow();
                        _wasShowing = false;
                    }
                }
            }
            else
            {
                if (gameHwnd == IntPtr.Zero)
                {
                    _gameHwnd = IntPtr.Zero;
                    if (_gameFoundBefore) _gameFoundBefore = false;
                }
                if (_wasShowing)
                {
                    HideOverlay();
                    HideLockWindow();
                    _wasShowing = false;
                }
            }
        }

        IntPtr FindGameWindow()
        {
            IntPtr result = IntPtr.Zero;
            EnumWindows((hwnd, _) =>
            {
                if (!IsWindowVisible(hwnd)) return true;
                var sb = new StringBuilder(256);
                GetWindowText(hwnd, sb, 256);
                string title = sb.ToString().Trim();

                foreach (var gt in GameTitles)
                {
                    if (title == gt || title.StartsWith(gt))
                    {
                        // Use GetWindowRect here (just for existence check, not positioning)
                        if (GetWindowRect(hwnd, out var r)
                            && (r.Right - r.Left) > 200
                            && (r.Bottom - r.Top) > 200)
                        {
                            result = hwnd;
                            return false;
                        }
                    }
                }
                return true;
            }, IntPtr.Zero);
            return result;
        }

        void PositionOverlay()
        {
            if (_gameHwnd == IntPtr.Zero) return;
            if (GetGameVisibleRect(_gameHwnd, out var r))
            {
                double gameW = r.Right - r.Left;
                switch (_preset)
                {
                    case 3: // Vertical left
                        Left = r.Left + 20;
                        Top = r.Top + 60;
                        break;
                    default: // Preset 1, 2: centered top
                        Left = r.Left + (gameW - ActualWidth) / 2;
                        Top = r.Top + 40;
                        break;
                }
            }
        }

        /// <summary>
        /// Get the visible bounds of the game window, excluding invisible DWM borders.
        /// Falls back to GetWindowRect if DWM API is unavailable.
        /// </summary>
        bool GetGameVisibleRect(IntPtr hwnd, out RECT rect)
        {
            // DwmGetWindowAttribute with EXTENDED_FRAME_BOUNDS returns the actual
            // visible area, excluding the invisible ~7px DWM border on Win10/11
            int hr = DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
                         out rect, Marshal.SizeOf<RECT>());
            if (hr == 0) return true;
            // Fallback for non-DWM scenarios
            return GetWindowRect(hwnd, out rect);
        }

        void ShowOverlay()
        {
            if (!_overlayVisible)
            {
                Show();
                Topmost = true;
                _overlayVisible = true;
            }
        }

        void HideOverlay()
        {
            if (_overlayVisible)
            {
                Hide();
                _overlayVisible = false;
            }
        }

        // ── HTTP Helpers ────────────────────────────────────────────

        async System.Threading.Tasks.Task<JsonElement?> GetJsonAsync(string url)
        {
            try
            {
                string json = await _http.GetStringAsync(url);
                return JsonDocument.Parse(json).RootElement;
            }
            catch { return null; }
        }

        async System.Threading.Tasks.Task PostConfigAsync(Dictionary<string, object> data)
        {
            try
            {
                string json = JsonSerializer.Serialize(data);
                await _http.PostAsync(
                    $"{_apiBase}/overlay/config",
                    new StringContent(json, Encoding.UTF8, "application/json"));
            }
            catch { }
        }

        static double? GetNum(JsonElement? el, string key)
        {
            if (el?.TryGetProperty(key, out var v) == true)
            {
                if (v.ValueKind == JsonValueKind.Number) return v.GetDouble();
                if (v.ValueKind == JsonValueKind.String
                    && double.TryParse(v.GetString(), out double d)) return d;
            }
            return null;
        }

        static string? GetStr(JsonElement? el, string key)
        {
            if (el?.TryGetProperty(key, out var v) == true)
                return v.ValueKind == JsonValueKind.String
                    ? v.GetString() : v.ToString();
            return null;
        }

        static bool? GetBool(JsonElement? el, string key)
        {
            if (el?.TryGetProperty(key, out var v) == true)
            {
                if (v.ValueKind == JsonValueKind.True) return true;
                if (v.ValueKind == JsonValueKind.False) return false;
            }
            return null;
        }

        static string[]? GetStrArray(JsonElement? el, string key)
        {
            if (el?.TryGetProperty(key, out var v) == true
                && v.ValueKind == JsonValueKind.Array)
            {
                return v.EnumerateArray()
                    .Select(e => e.GetString()!)
                    .ToArray();
            }
            return null;
        }

        // ── Format Helpers ──────────────────────────────────────────

        static string FormatFE(double v) => $"{v:N1}";

        static string FormatTime(double sec)
        {
            if (sec < 0) return "--:--";
            int s = (int)sec;
            int h = s / 3600, m = (s % 3600) / 60, ss = s % 60;
            return h > 0 ? $"{h}:{m:D2}:{ss:D2}" : $"{m:D2}:{ss:D2}";
        }
    }
}
