@echo off
echo Installing PyInstaller...
pip install pyinstaller

echo.
echo Building UTM Professional App...
echo This may take a few minutes. Please wait...

:: Compile the application into a single directory (not a single file) 
:: because we need external folders like 'reports' and 'config' to sit next to it.
pyinstaller --noconfirm --onedir --windowed --name "UTM_Professional"  "UTM_Professional/main.py"

echo.
echo ==================================================
echo BUILD COMPLETE!
echo Your application is located in the "dist\UTM_Professional" folder.
echo You can double-click "UTM_Professional.exe" inside that folder to run it.
echo ==================================================
pause
