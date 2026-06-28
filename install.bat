@echo off
chcp 65001 >nul
title Vast.ai GPU 管理工具 - 安装程序

echo ============================================
echo    Vast.ai GPU 管理工具 - 一键安装
echo ============================================
echo.

:: 查找系统 Python（排除 venv 目录）
set PYTHON_CMD=

for /f "tokens=*" %%p in ('where python 2^>nul') do (
    echo %%p | findstr /i "venv" >nul 2>&1
    if %errorlevel% neq 0 (
        if not defined PYTHON_CMD (
            "%%p" -m pip --version >nul 2>&1
            if %errorlevel% equ 0 set "PYTHON_CMD=%%p"
        )
    )
)

if not defined PYTHON_CMD (
    for /f "tokens=2*" %%a in ('reg query "HKCU\Software\Python\PythonCore" /s /v ExecutablePath 2^>nul ^| findstr /i "python.exe"') do (
        echo %%b | findstr /i "venv" >nul 2>&1
        if %errorlevel% neq 0 if not defined PYTHON_CMD (
            "%%b" -m pip --version >nul 2>&1
            if %errorlevel% equ 0 set "PYTHON_CMD=%%b"
        )
    )
)

if not defined PYTHON_CMD (
    for %%d in (
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
    ) do (
        if not defined PYTHON_CMD (
            if exist %%d (
                %%d -m pip --version >nul 2>&1
                if %errorlevel% equ 0 set "PYTHON_CMD=%%d"
            )
        )
    )
)

if not defined PYTHON_CMD (
    echo [!] 未检测到 Python，正在下载安装...
    curl -L -o "%TEMP%\python_installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    if %errorlevel% neq 0 (
        echo [错误] Python 下载失败，请手动安装。
        pause
        exit /b 1
    )
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    set PYTHON_CMD=py -3
    echo [√] Python 安装完成
) else (
    for /f "tokens=*" %%v in ('"%PYTHON_CMD%" --version 2^>^&1') do echo [√] 已检测到 %%v
)

echo.
set INSTALL_DIR=%USERPROFILE%\vast-manager
echo [1/3] 下载程序文件...

if exist "%INSTALL_DIR%" (
    echo     检测到旧版本，正在更新...
    cd /d "%INSTALL_DIR%"
    git pull >nul 2>&1
    if %errorlevel% neq 0 (
        rmdir /s /q "%INSTALL_DIR%"
        git clone https://github.com/gongxianga/vast-manager.git "%INSTALL_DIR%" >nul 2>&1
    )
) else (
    git clone https://github.com/gongxianga/vast-manager.git "%INSTALL_DIR%" >nul 2>&1
    if %errorlevel% neq 0 (
        echo [错误] 下载失败，请检查网络连接。
        pause
        exit /b 1
    )
)
echo [√] 文件下载完成

echo.
echo [2/3] 安装依赖库...
"%PYTHON_CMD%" -m pip install requests --quiet
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败。
    pause
    exit /b 1
)
echo [√] 依赖安装完成

echo.
echo [3/3] 创建桌面快捷方式...
set SHORTCUT=%USERPROFILE%\Desktop\Vast管理工具.bat
(
    echo @echo off
    echo chcp 65001 ^>nul
    echo cd /d "%INSTALL_DIR%"
    echo "%PYTHON_CMD%" vast.py
    echo pause
) > "%SHORTCUT%"
echo [√] 桌面快捷方式已创建

echo.
echo ============================================
echo    安装完成！
echo ============================================
echo.
echo 首次运行需要输入 Vast.ai API Key
echo 获取地址: cloud.vast.ai ^> Account ^> API Key
echo.
set /p START=是否立即启动程序？(y/n):
if /i "%START%"=="y" (
    cd /d "%INSTALL_DIR%"
    "%PYTHON_CMD%" vast.py
)
