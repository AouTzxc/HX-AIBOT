$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$appName = "HX-AIBOT"
$distDir = Join-Path $projectRoot "dist"
$bundleDir = Join-Path $distDir $appName
$zipPath = Join-Path $distDir ($appName + "_portable.zip")
$iconPath = Join-Path $projectRoot "HXlogo.ico"

if (Test-Path $bundleDir) {
    Remove-Item -LiteralPath $bundleDir -Recurse -Force
}

if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name $appName `
    --icon $iconPath `
    --optimize 2 `
    --collect-all pyautogui `
    --collect-all mouseinfo `
    --collect-all pyscreeze `
    --collect-all rapidocr_onnxruntime `
    --collect-all onnxruntime `
    --exclude-module matplotlib `
    --exclude-module pandas `
    --exclude-module scipy `
    --exclude-module IPython `
    --exclude-module jupyter_client `
    --exclude-module jupyter_core `
    --exclude-module notebook `
    --exclude-module pytest `
    --exclude-module PyQt5 `
    --exclude-module PyQt6 `
    --exclude-module PySide2 `
    --exclude-module torch `
    --exclude-module torchvision `
    --exclude-module torchaudio `
    --exclude-module tensorflow `
    --exclude-module tensorboard `
    --exclude-module onnx `
    --exclude-module onnxruntime.datasets `
    --exclude-module onnxruntime.tools `
    --exclude-module onnxruntime.transformers `
    --exclude-module onnxruntime.quantization `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtPdf `
    qt_app.py

Start-Sleep -Seconds 5
Compress-Archive -Path $bundleDir -DestinationPath $zipPath -Force
Write-Host "打包完成: $bundleDir"
Write-Host "压缩包: $zipPath"
