$ErrorActionPreference = 'SilentlyContinue'
$installDirectory = [IO.Path]::GetFullPath($PSScriptRoot)
$startMenuShortcut = Join-Path ([Environment]::GetFolderPath('Programs')) 'MOON.lnk'
$desktopShortcut = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'MOON.lnk'
$uninstallKeyPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\MOON'
$installedOptions = Get-ItemProperty -LiteralPath $uninstallKeyPath
if ($installedOptions.StartMenuShortcut -eq 1) {
    Remove-Item -LiteralPath $startMenuShortcut -Force
}
if ($installedOptions.DesktopShortcut -eq 1) {
    Remove-Item -LiteralPath $desktopShortcut -Force
}
Remove-Item -LiteralPath $uninstallKeyPath -Recurse -Force

# Delete only files owned by this installer. Remove the folder only if it is empty.
$cleanupScript = Join-Path $env:TEMP ("MOON-uninstall-" + [guid]::NewGuid().ToString('N') + '.ps1')
$escapedDirectory = $installDirectory.Replace("'", "''")
$escapedCleanup = $cleanupScript.Replace("'", "''")
Set-Content -LiteralPath $cleanupScript -Encoding UTF8 -Value @"
Start-Sleep -Seconds 2
`$safeDirectory = '$escapedDirectory'
`$safeCleanup = '$escapedCleanup'
Remove-Item -LiteralPath (Join-Path `$safeDirectory 'MOON.exe') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path `$safeDirectory 'Uninstall-MOON.ps1') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath `$safeDirectory -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath `$safeCleanup -Force -ErrorAction SilentlyContinue
"@
Start-Process -FilePath 'powershell.exe' -WindowStyle Hidden -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $cleanupScript)
