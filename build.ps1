<#
Сборка Restore: dist\RestoreAppStore.exe (PyInstaller) и dist\RestoreSetup-<версия>.exe (Inno Setup 6).

  powershell -ExecutionPolicy Bypass -File build.ps1                 # exe + установщик
  powershell -ExecutionPolicy Bypass -File build.ps1 -SkipInstaller  # только exe

Нужно: Python 3.12 (py install 3.12), для установщика — Inno Setup 6.
ipatool и Unicorn скачиваются из официальных релизов на GitHub; сборка останавливается, если не совпал SHA-256.
#>
param([switch]$SkipInstaller)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$IpatoolUrl = "https://github.com/majd/ipatool/releases/download/v2.7.0/ipatool-2.7.0-windows-amd64.tar.gz"
$IpatoolSha = "b729608716908be287c2e6972f9e8cd05f879810ae5d182fc856c9e57cca0dd5"  # ipatool-2.7.0-windows-amd64.tar.gz.sha256sum
$UnicornUrl = "https://github.com/unicorn-engine/unicorn/releases/download/2.1.4/windows-mingw64-shared.7z"
$UnicornSha = "0960f938e66fa12c448742bddd2a03aa88abeeb2b3cda7156493a2da86228d3a"  # digest ассета в релизе 2.1.4
$UnicornDllSha = "d8f9a89222ffa74493a1d47090e17f8e1db8ac171a3128c6a76a4ea09de11469"  # = UNICORN_SHA256 в restore_apps_gui.py
$UnicornLicenseUrl = "https://raw.githubusercontent.com/unicorn-engine/unicorn/2.1.4/COPYING"

function Assert-Hash($path, $sha) {
    $h = (Get-FileHash $path -Algorithm SHA256).Hash
    if ($h -ne $sha) { throw "SHA-256 не совпал: $path`n  ожидался $sha`n  получен  $h" }
}

function Get-Checked($url, $out, $sha) {
    if (-not (Test-Path $out) -or (Get-FileHash $out -Algorithm SHA256).Hash -ne $sha) {
        Write-Host "Скачиваю $url"
        $ProgressPreference = "SilentlyContinue"
        Invoke-WebRequest $url -OutFile $out
    }
    Assert-Hash $out $sha
}

function Invoke-Native {
    & $args[0] @($args | Select-Object -Skip 1)
    if ($LASTEXITCODE) { throw "Команда завершилась с кодом ${LASTEXITCODE}: $($args -join ' ')" }
}

# --- окружение сборки ---
$py = "build\venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Создаю build\venv (Python 3.12)"
    Invoke-Native py -V:3.12 -m venv build\venv
}
Invoke-Native $py -m pip install --disable-pip-version-check -q -r requirements-build.txt

# --- внешние компоненты ---
New-Item -ItemType Directory -Force build\dl, build\res | Out-Null

Get-Checked $IpatoolUrl build\dl\ipatool.tar.gz $IpatoolSha
Remove-Item -Recurse -Force build\dl\ipatool -ErrorAction SilentlyContinue
New-Item -ItemType Directory build\dl\ipatool | Out-Null
Invoke-Native tar -xzf build\dl\ipatool.tar.gz -C build\dl\ipatool
$ipatoolExe = Get-ChildItem build\dl\ipatool -Recurse -Filter "ipatool*.exe" | Select-Object -First 1
if (-not $ipatoolExe) { throw "В архиве ipatool нет exe" }
Copy-Item $ipatoolExe.FullName build\res\ipatool.exe -Force

Get-Checked $UnicornUrl build\dl\unicorn.7z $UnicornSha
Remove-Item -Recurse -Force build\dl\unicorn -ErrorAction SilentlyContinue
Invoke-Native $py -m py7zr x build\dl\unicorn.7z build\dl\unicorn
$dll = Get-ChildItem build\dl\unicorn -Recurse -Filter "libunicorn.dll" | Select-Object -First 1
if (-not $dll) { throw "В архиве Unicorn нет libunicorn.dll" }
Assert-Hash $dll.FullName $UnicornDllSha
Copy-Item $dll.FullName build\res\libunicorn.dll -Force
if (-not (Test-Path build\res\UNICORN_COPYING.txt)) {
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest $UnicornLicenseUrl -OutFile build\res\UNICORN_COPYING.txt
}

# --- тесты: сломанную логику не собираем ---
Write-Host "Тесты"
Invoke-Native $py -m unittest discover -s tests -q

# --- exe: портативный одним файлом и папкой для установщика (см. RestoreAppStore.spec) ---
if (-not (Test-Path assets\icon.ico)) { Invoke-Native $py tools\make_icon.py }
$version = (& $py tools\write_version_info.py build\version_info.txt).Trim()
if ($LASTEXITCODE) { throw "Не удалось записать версию" }
foreach ($onedir in "0", "1") {
    $env:RESTORE_ONEDIR = $onedir
    Write-Host ("Собираю RestoreAppStore $version " + $(if ($onedir -eq "1") { "(папкой)" } else { "(одним файлом)" }))
    Invoke-Native build\venv\Scripts\pyinstaller.exe RestoreAppStore.spec --noconfirm --log-level WARN --workpath "build\work$onedir" --distpath dist
}
Remove-Item Env:RESTORE_ONEDIR

# собранный интерфейс загружается без ошибок (иначе из Qt вырезано что-то нужное — см. DROP в spec)
foreach ($exe in "dist\RestoreAppStore\RestoreAppStore.exe", "dist\RestoreAppStore.exe") {
    $report = Join-Path $PWD "build\check-ui.txt"
    $p = Start-Process $exe -ArgumentList "--check-ui", "`"$report`"" -Wait -PassThru -WindowStyle Hidden
    if ($p.ExitCode -ne 0) { throw "Интерфейс в $exe не загрузился:`n" + (Get-Content $report -Raw -ErrorAction SilentlyContinue) }
    Write-Host "Интерфейс загружается: $exe"
}
$outputs = @("dist\RestoreAppStore.exe")

# --- установщик ---
if (-not $SkipInstaller) {
    $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
              "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) { throw "Не найден Inno Setup 6 (ISCC.exe). Установите: winget install JRSoftware.InnoSetup — или запустите с -SkipInstaller." }
    Write-Host "Собираю установщик"
    Invoke-Native $iscc /Q "/DAppVersion=$version" installer\RestoreSetup.iss
    $outputs += "dist\RestoreSetup-$version.exe"
}

# контрольные суммы — для страницы релиза
$sums = $outputs | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_ -Algorithm SHA256).Hash.ToLower(), (Split-Path $_ -Leaf) }
$sums | Set-Content dist\SHA256SUMS.txt -Encoding ascii
$sums | ForEach-Object { Write-Host $_ }
