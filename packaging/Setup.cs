using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class Setup
{
    private const string ProductName = "MOON";
    private const string Version = "1.0.6";
    private static string InstallDirectory;

    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new SetupForm());
    }

    private sealed class SetupForm : Form
    {
        private readonly Label _status;
        private readonly Button _install;
        private readonly TextBox _directory;
        private readonly CheckBox _startMenuShortcut;
        private readonly CheckBox _desktopShortcut;

        public SetupForm()
        {
            Text = "MOON Setup";
            ClientSize = new Size(700, 500);
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            BackColor = Color.FromArgb(13, 18, 34);
            ForeColor = Color.FromArgb(238, 242, 255);
            Font = new Font("Segoe UI", 9F);

            string defaultDirectory = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Programs",
                ProductName);

            var header = new Panel
            {
                Left = 0,
                Top = 0,
                Width = ClientSize.Width,
                Height = 132,
                BackColor = Color.FromArgb(20, 28, 52)
            };
            header.Paint += DrawHeader;

            var eyebrow = MakeLabel("MOON  /  INSTALLER", 28, 22, 300, 20, 8.5F, true,
                Color.FromArgb(137, 180, 255));
            var title = MakeLabel("Установка MOON", 28, 46, 520, 42, 24F, true,
                Color.FromArgb(248, 250, 255));
            var subtitle = MakeLabel("Ваш лаунчер приложений — в нескольких шагах от запуска.",
                30, 91, 590, 24, 10F, false, Color.FromArgb(177, 190, 218));
            header.Controls.AddRange(new Control[] { eyebrow, title, subtitle });

            var sectionTitle = MakeLabel("Место установки", 30, 153, 350, 26, 14F, true,
                Color.FromArgb(239, 243, 255));
            var sectionDetail = MakeLabel("Выберите папку, где будут храниться файлы MOON.",
                31, 180, 620, 22, 9F, false, Color.FromArgb(157, 171, 200));
            var pathSurface = new Panel
            {
                Left = 30,
                Top = 211,
                Width = 640,
                Height = 50,
                BackColor = Color.FromArgb(23, 31, 51)
            };
            _directory = new TextBox
            {
                Left = 12,
                Top = 12,
                Width = 500,
                Height = 26,
                BorderStyle = BorderStyle.None,
                BackColor = pathSurface.BackColor,
                ForeColor = Color.FromArgb(226, 233, 249),
                Font = new Font("Segoe UI", 9.5F),
                Text = defaultDirectory
            };
            var browse = MakeButton("Обзор", 524, 8, 104, 34,
                Color.FromArgb(35, 48, 76), Color.FromArgb(231, 238, 255),
                Color.FromArgb(61, 81, 122));
            browse.Click += BrowseClicked;
            pathSurface.Controls.AddRange(new Control[] { _directory, browse });

            var shortcutsTitle = MakeLabel("Ярлыки", 30, 280, 260, 24, 12F, true,
                Color.FromArgb(230, 236, 252));
            _startMenuShortcut = MakeCheckBox("Добавить MOON в меню «Пуск»", 31, 312, true);
            _desktopShortcut = MakeCheckBox("Создать ярлык на рабочем столе", 345, 312, false);

            var privacyCard = new Panel
            {
                Left = 30,
                Top = 355,
                Width = 640,
                Height = 58,
                BackColor = Color.FromArgb(19, 37, 49)
            };
            var privacyDot = MakeLabel("●", 13, 13, 20, 20, 10F, true,
                Color.FromArgb(96, 220, 184));
            var privacy = MakeLabel(
                "В установщик входят только приложение и деинсталлятор.\nНастройки, личные файлы и данные профиля не копируются.",
                36, 9, 585, 42, 8.5F, false, Color.FromArgb(177, 218, 211));
            privacyCard.Controls.AddRange(new Control[] { privacyDot, privacy });

            _status = MakeLabel("Папка по умолчанию — только для вашей учётной записи Windows.",
                31, 430, 440, 28, 8.5F, false, Color.FromArgb(155, 170, 199));
            _install = MakeButton("Установить", 462, 428, 122, 40,
                Color.FromArgb(105, 142, 255), Color.White, Color.FromArgb(105, 142, 255));
            _install.Font = new Font("Segoe UI", 9.5F, FontStyle.Bold);
            _install.Click += InstallClicked;
            var cancel = MakeButton("Отмена", 592, 428, 78, 40,
                Color.FromArgb(28, 36, 57), Color.FromArgb(206, 216, 239),
                Color.FromArgb(50, 63, 92));
            cancel.DialogResult = DialogResult.Cancel;

            Controls.AddRange(new Control[]
            {
                header, sectionTitle, sectionDetail, pathSurface, shortcutsTitle,
                _startMenuShortcut, _desktopShortcut, privacyCard, _status, _install, cancel
            });
            AcceptButton = _install;
            CancelButton = cancel;
        }

        private static Label MakeLabel(string text, int left, int top, int width, int height,
            float size, bool bold, Color color)
        {
            return new Label
            {
                Text = text,
                Left = left,
                Top = top,
                Width = width,
                Height = height,
                ForeColor = color,
                Font = new Font("Segoe UI", size, bold ? FontStyle.Bold : FontStyle.Regular),
                AutoSize = false
            };
        }

        private static CheckBox MakeCheckBox(string text, int left, int top, bool isChecked)
        {
            return new CheckBox
            {
                Text = text,
                Left = left,
                Top = top,
                Width = 310,
                Height = 25,
                Checked = isChecked,
                ForeColor = Color.FromArgb(215, 224, 245),
                BackColor = Color.Transparent,
                Font = new Font("Segoe UI", 9F)
            };
        }

        private static Button MakeButton(string text, int left, int top, int width, int height,
            Color background, Color foreground, Color border)
        {
            var button = new Button
            {
                Text = text,
                Left = left,
                Top = top,
                Width = width,
                Height = height,
                FlatStyle = FlatStyle.Flat,
                BackColor = background,
                ForeColor = foreground,
                Font = new Font("Segoe UI", 9F),
                Cursor = Cursors.Hand
            };
            button.FlatAppearance.BorderColor = border;
            button.FlatAppearance.BorderSize = 1;
            button.FlatAppearance.MouseOverBackColor = ControlPaint.Light(background, 0.08F);
            button.FlatAppearance.MouseDownBackColor = ControlPaint.Dark(background, 0.08F);
            return button;
        }

        private static void DrawHeader(object sender, PaintEventArgs e)
        {
            var panel = (Panel)sender;
            using (var brush = new LinearGradientBrush(panel.ClientRectangle,
                Color.FromArgb(25, 39, 75), Color.FromArgb(21, 27, 49), 0F))
                e.Graphics.FillRectangle(brush, panel.ClientRectangle);

            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            using (var glow = new SolidBrush(Color.FromArgb(28, 119, 158, 255)))
                e.Graphics.FillEllipse(glow, panel.Width - 200, -90, 245, 245);
            using (var moon = new SolidBrush(Color.FromArgb(151, 178, 255)))
                e.Graphics.FillEllipse(moon, panel.Width - 110, 39, 42, 42);
            using (var shadow = new SolidBrush(Color.FromArgb(25, 34, 61)))
                e.Graphics.FillEllipse(shadow, panel.Width - 96, 31, 39, 39);
        }

        private void BrowseClicked(object sender, EventArgs e)
        {
            using (var dialog = new FolderBrowserDialog())
            {
                dialog.Description = "Выберите папку для установки MOON";
                dialog.ShowNewFolderButton = true;
                if (Directory.Exists(_directory.Text))
                    dialog.SelectedPath = _directory.Text;
                if (dialog.ShowDialog(this) == DialogResult.OK)
                    _directory.Text = dialog.SelectedPath;
            }
        }

        private void InstallClicked(object sender, EventArgs e)
        {
            _install.Enabled = false;
            _status.Text = "Подготавливаем файлы MOON…";
            try
            {
                if (String.IsNullOrWhiteSpace(_directory.Text))
                    throw new InvalidOperationException("Укажите папку установки.");

                InstallDirectory = Path.GetFullPath(_directory.Text.Trim());
                string executable = Path.Combine(InstallDirectory, "MOON.exe");
                string uninstaller = Path.Combine(InstallDirectory, "Uninstall-MOON.ps1");
                bool replacing = File.Exists(executable) || File.Exists(uninstaller);
                if (replacing && MessageBox.Show(this,
                    "В этой папке уже есть файлы MOON. Заменить только MOON.exe и деинсталлятор? Остальные файлы и папки останутся нетронутыми.",
                    "Обновление MOON", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                {
                    _status.Text = "Установка отменена. Существующие файлы не изменены.";
                    _install.Enabled = true;
                    return;
                }

                Directory.CreateDirectory(InstallDirectory);
                CopyResource("MOON.exe", executable);
                CopyResource("Uninstall.ps1", uninstaller);

                string startMenu = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.Programs), "MOON.lnk");
                string desktop = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "MOON.lnk");
                if (_startMenuShortcut.Checked)
                    CreateShortcut(startMenu, executable, InstallDirectory);
                if (_desktopShortcut.Checked)
                    CreateShortcut(desktop, executable, InstallDirectory);

                RegisterUninstaller(_startMenuShortcut.Checked, _desktopShortcut.Checked);
                _directory.Enabled = false;
                _startMenuShortcut.Enabled = false;
                _desktopShortcut.Enabled = false;
                _status.Text = "MOON установлена. Ваши пользовательские файлы не затронуты.";
                _install.Text = "Запустить";
                _install.Enabled = true;
                _install.Click -= InstallClicked;
                _install.Click += LaunchClicked;
            }
            catch (Exception error)
            {
                _status.Text = "Не удалось завершить установку.";
                _install.Enabled = true;
                MessageBox.Show(this, error.Message, "Установка MOON",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void LaunchClicked(object sender, EventArgs e)
        {
            Process.Start(new ProcessStartInfo(Path.Combine(InstallDirectory, "MOON.exe"))
            {
                UseShellExecute = true,
                WorkingDirectory = InstallDirectory
            });
            Close();
        }

        private static void CopyResource(string resourceName, string destination)
        {
            using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream(resourceName))
            {
                if (input == null)
                    throw new InvalidOperationException("В установщике отсутствует файл " + resourceName + ".");
                using (FileStream output = File.Create(destination))
                    input.CopyTo(output);
            }
        }

        private static void CreateShortcut(string shortcutPath, string targetPath, string workingDirectory)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(shortcutPath));
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            object shell = Activator.CreateInstance(shellType);
            object shortcut = shellType.InvokeMember(
                "CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { shortcutPath });
            Type shortcutType = shortcut.GetType();
            shortcutType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
            shortcutType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { workingDirectory });
            shortcutType.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath + ",0" });
            shortcutType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
        }

        private static void RegisterUninstaller(bool createStartMenuShortcut, bool createDesktopShortcut)
        {
            string uninstallKey = @"Software\Microsoft\Windows\CurrentVersion\Uninstall\MOON";
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(uninstallKey))
            {
                key.SetValue("DisplayName", Setup.ProductName);
                key.SetValue("DisplayVersion", Version);
                key.SetValue("Publisher", Setup.ProductName);
                key.SetValue("InstallLocation", InstallDirectory);
                key.SetValue("StartMenuShortcut", createStartMenuShortcut ? 1 : 0, RegistryValueKind.DWord);
                key.SetValue("DesktopShortcut", createDesktopShortcut ? 1 : 0, RegistryValueKind.DWord);
                key.SetValue("UninstallString", "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"" +
                    Path.Combine(InstallDirectory, "Uninstall-MOON.ps1") + "\"");
                key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
            }
        }
    }
}
