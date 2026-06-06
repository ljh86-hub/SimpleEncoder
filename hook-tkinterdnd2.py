from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import tkinterdnd2, os

datas = collect_data_files('tkinterdnd2')
binaries = collect_dynamic_libs('tkinterdnd2')

# tkdnd dll 직접 포함
pkg_dir = os.path.dirname(tkinterdnd2.__file__)
for root, dirs, files in os.walk(pkg_dir):
    for f in files:
        if f.endswith('.dll') or f.endswith('.tcl') or f.endswith('.so'):
            src = os.path.join(root, f)
            rel = os.path.relpath(root, os.path.dirname(pkg_dir))
            datas.append((src, rel))
