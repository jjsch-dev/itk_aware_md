from kivy_deps import sdl2, glew
from kivymd import hooks_path as kivymd_hooks_path

block_cipher = None

a = Analysis(['main.py'],
             pathex=['itk-aware'],
             binaries=[],
             datas=[('layout.kv', '.'),
                    ('images/distance_2_red.png', 'images/'),
                    ('images/Tux.png', 'images/'),
                    ('images/itk_logo_transparent.png', 'images/'),
                    ('images/Windows_2012.png', 'images/'),
                    ('images/Android_robot.png', 'images/'),
                    ('images/cpu_color.png', 'images/')],
             hiddenimports=['win32timezone'],
             hookspath=[kivymd_hooks_path],
             runtime_hooks=[],
             excludes= [],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False) 

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='itk_aware',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon='images/distance_2_red.ico' )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               *[Tree(p) for p in (sdl2.dep_bins + glew.dep_bins)],
               strip=False,
               upx=True,
               upx_exclude=[],
               name='itk_aware')