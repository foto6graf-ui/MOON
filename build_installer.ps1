$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$compiler = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$application = Join-Path $root 'Output\MOON-1.0.6.exe'
$icon = Join-Path $root 'assets\moon.ico'
$source = Join-Path $root 'packaging\Setup.cs'
$uninstaller = Join-Path $root 'packaging\Uninstall.ps1'
$outputDirectory = Join-Path $root 'Output'
$output = Join-Path $outputDirectory 'MOON-Setup-v1.0.6.exe'

if (-not (Test-Path -LiteralPath $application)) { throw 'Build Output\MOON-1.0.6.exe before creating the installer.' }
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Microsoft .NET Framework C# compiler was not found.' }
if (-not (Test-Path -LiteralPath $icon)) { throw 'MOON installer icon was not found.' }
if (-not (Test-Path -LiteralPath $source)) { throw 'Installer source was not found.' }
if (-not (Test-Path -LiteralPath $uninstaller)) { throw 'Installer uninstaller was not found.' }

# The installer embeds only the built application and its uninstaller. It never
# gathers files from the project, user profile, settings, environment, or cache.
$sensitiveProjectFiles = @('.env', 'settings.json', 'settings.local.json')
foreach ($relativePath in $sensitiveProjectFiles) {
    $candidate = Join-Path $root $relativePath
    if (Test-Path -LiteralPath $candidate) {
        Write-Host "Excluded from installer: $relativePath"
    }
}

New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
& $compiler /nologo /codepage:65001 /target:winexe "/out:$output" "/win32icon:$icon" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/resource:$application,MOON.exe" "/resource:$uninstaller,Uninstall.ps1" $source
if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed with exit code $LASTEXITCODE." }
Get-Item -LiteralPath $output | Select-Object FullName,Length,LastWriteTime
