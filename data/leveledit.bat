@echo off
set PATH=C:\Python26;%PATH%
set PYTHONPATH=C:\Dev\python\pyweek\pgu-0.16;%PYTHONPATH%
python C:\Dev\python\pyweek\pgu-0.16\scripts\leveledit map.tga tiles.tga codes.tga 32 32 --sw 1280 --sh 760
pause
cls
