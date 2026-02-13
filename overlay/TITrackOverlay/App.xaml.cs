using System;
using System.Windows;

namespace TITrackOverlay
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            string host = "127.0.0.1";
            int port = 8000;

            var args = e.Args;
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--host" && i + 1 < args.Length)
                    host = args[++i];
                else if (args[i] == "--port" && i + 1 < args.Length)
                    port = int.Parse(args[++i]);
            }

            var window = new MainWindow(host, port);
            // Show briefly to initialize HWND - OnSourceInitialized will Hide() immediately
            window.Show();
        }
    }
}
