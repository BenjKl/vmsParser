# -*- mode: python -*-

block_cipher = None


a = Analysis(['vmsParser.py'],
             pathex=['/Users/benjamin/Documents/python/PyQt/vmsParser'],
             binaries=[],
             datas=[('gui.ui', '.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

# First, generate an executable file
# Notice that the icon is a .icns file - Apple's icon format
# Also note that console=True
import sys
if sys.platform.startswith('darwin'):
    exe = EXE(pyz,
            a.scripts,
            exclude_binaries=True,
            name='vmsParser',
            debug=False,
            strip=True,
            upx=True,
            console=False,
            icon='icon_XPS.icns')

    coll=COLLECT(exe,
            a.binaries,
            a.datas,
            name='vmsParser',
            strip=True,
            upx=True)

# Package the executable file into .app if on OS X

if sys.platform.startswith('darwin'):
   app = BUNDLE(coll,
                name='vmsParser.app', 
                #For Retina Display
                info_plist={'NSHighResolutionCapable': 'True'},
                icon='icon_XPS.icns'
               )


# Run 'codesign --remove-signature Python' on Python file in App