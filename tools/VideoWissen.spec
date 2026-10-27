# Build on Windows with: python -m PyInstaller tools/VideoWissen.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, copy_metadata

project = Path(SPECPATH).parent
vendor = next((project / '.build/vendor/ffmpeg').glob('*/bin'))
datas, binaries, hiddenimports = [], [], []
for package in ('faster_whisper', 'ctranslate2', 'tokenizers', 'onnxruntime'):
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
for distribution in ('faster-whisper', 'huggingface-hub', 'ctranslate2', 'tokenizers', 'onnxruntime', 'numpy'):
    datas += copy_metadata(distribution)
for path in vendor.iterdir():
    if path.suffix.lower() == '.dll' or path.name == 'ffmpeg.exe':
        binaries.append((str(path), 'ffmpeg'))

a = Analysis([str(project / 'app.py')], pathex=[str(project)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
             runtime_hooks=[str(project / 'tools/runtime_pcm_audio.py')],
             excludes=['av', 'faster_whisper.audio', 'imageio_ffmpeg', 'torch', 'tensorflow', 'transformers', 'scipy', 'pandas',
                       'matplotlib', 'pytest', 'pip', 'setuptools'], noarchive=False)
# Keep the shared FFmpeg DLLs only beside ffmpeg.exe, not a second copy in _internal/.
vendor_names = {path.name.lower() for path in vendor.glob('*.dll')}
a.binaries = [entry for entry in a.binaries if not (
    (Path(entry[0]).parent == Path('.') and Path(entry[0]).name.lower() in vendor_names)
    or Path(entry[0]).name.lower() == 'cudnn64_9.dll')]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='VideoWissen', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
          codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='VideoWissen')
