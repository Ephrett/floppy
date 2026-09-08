# Builds FLOPPY.exe with PyInstaller. Never ships .env, state, seeds or backups (see .gitignore).
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$d = $PSScriptRoot; $py = if ($env:PYTHON) { $env:PYTHON } else { 'python' }; Set-Location $d
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
if (Select-String -Path "$d\engine\*.py", "$d\app.py" -Pattern '[0-9]{8,10}:[A-Za-z0-9_-]{30,}' -Quiet) { 'token-looking string in sources - aborting'; exit 1 }
& $py -m PyInstaller --noconfirm --clean --windowed --name FLOPPY --icon assets\floppy.ico --add-data 'ui;ui' --add-data 'engine;engine' --add-data 'fake_worker.py;.' --collect-all cryptography --collect-all webview --hidden-import runpy app.py *> build.log
if (Test-Path dist\FLOPPY\FLOPPY.exe) { "built: " + [int]((Get-ChildItem dist\FLOPPY -Recurse | Measure-Object Length -Sum).Sum / 1MB) + " MB -> dist\FLOPPY\FLOPPY.exe" } else { Get-Content build.log -Tail 15; exit 1 }
