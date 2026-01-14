from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_options = {
    'packages': ['PySide6', 'api', 'core', 'sources', 'app'],
    'excludes': ['matplotlib', 'numpy', 'scipy', 'pandas'],
    'include_files': [('app.ico', '.'), ('config', 'config')],
}

executables = [
    Executable('desktop_app.py', base='gui', target_name='MultiSourceDownloader.exe', icon='app.ico')
]

setup(name='MultiSourceDownloader',
      version='2.0.0',
      description='Multi-Source Standard Document Downloader',
      options={'build_exe': build_options},
      executables=executables)
