param(
    [Parameter(Mandatory = $true)]
    [string]$AuthUrl
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$parsedUrl = $null
if (-not [Uri]::TryCreate($AuthUrl, [UriKind]::Absolute, [ref]$parsedUrl) -or
    $parsedUrl.Scheme -ne 'https' -or
    -not $parsedUrl.Host -or
    $parsedUrl.UserInfo) {
    throw 'AuthUrl must be an HTTPS address without embedded credentials.'
}

$pyinstaller = Get-Command 'pyinstaller' -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
    throw 'PyInstaller was not found. Activate the project Python environment and install requirements first.'
}

Push-Location $root
try {
    $env:MOON_BUILD_AUTH_URL = $AuthUrl.TrimEnd('/')
    & $pyinstaller.Source --clean --noconfirm 'MOON.spec'
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $builtApp = Join-Path $root 'dist\MOON.exe'
    $outputApp = Join-Path $root 'Output\MOON-1.0.6.exe'
    if (-not (Test-Path -LiteralPath $builtApp)) {
        throw 'PyInstaller did not create dist\MOON.exe.'
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $outputApp) -Force | Out-Null
    Copy-Item -LiteralPath $builtApp -Destination $outputApp -Force
    & (Join-Path $root 'build_installer.ps1')
    if ($LASTEXITCODE -ne 0) {
        throw "Installer creation failed with exit code $LASTEXITCODE."
    }
}
finally {
    Remove-Item Env:MOON_BUILD_AUTH_URL -ErrorAction SilentlyContinue
    Pop-Location
}
