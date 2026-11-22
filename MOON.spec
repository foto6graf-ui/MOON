# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

build_datas = [('styles', 'styles'), ('assets', 'assets')]
build_auth_url = os.environ.get('MOON_BUILD_AUTH_URL', '').strip().rstrip('/')
if build_auth_url:
    auth_url_file = Path('build') / 'moon_auth_url.txt'
    auth_url_file.parent.mkdir(parents=True, exist_ok=True)
    auth_url_file.write_text(build_auth_url, encoding='utf-8')
    build_datas.append((str(auth_url_file), '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=build_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MOON',
    icon='assets/moon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
