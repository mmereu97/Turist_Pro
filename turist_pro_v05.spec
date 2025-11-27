# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# --- LISTA FIȘIERELOR DE INCLUS (DATAS) ---
# Format: ('cale_sursa', 'cale_destinatie_in_exe')
# 1. Includem map_template.html obligatoriu
# 2. Includem modulul custom_data_manager.py
added_files = [
    ('map_template.html', '.'),
    ('custom_data_manager.py', '.')
]

a = Analysis(
    ['turist_pro_v05.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebChannel',
        'PySide6.QtPrintSupport',
        'PySide6.QtNetwork',
        'googlemaps',
        'dotenv',
        'openpyxl'  # Necesar pentru citire Excel in custom_data_manager
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='TuristPro_Assistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Setează console=True pentru a vedea erorile la început. 
    # Pune False doar când ești sigur că totul merge perfect.
    console=True, 
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # Daca ai o iconita, decomenteaza linia si pune numele fisierului
)