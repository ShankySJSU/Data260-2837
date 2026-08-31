@echo off
echo Starting 40 nondeterminism runs...
echo.


REM ==Excuting my pthon program for 20 times at 0.7 temp
echo Excuting my pthon program for 20 times at 0.7 temp
for /l %%i in (1,1,20) do (
    echo Run %%i at temp 0.7y
    python agents_demo.py --input nondeterminism_input.json --temperature 0.7 > reports/hw01/raw/run_07_%%i.txt
)

echo.
echo Finished temp 0.7 runs.

REM == Excuting my pthon program for 20 times at  temperature 0.0 ====
echo Excuting my pthon program for 20 times at 0.0 temp
for /l %%i in (1,1,20) do (
    echo Run %%i at temp 0.0
    python agents_demo.py --input /nondeterminism_input.json --temperature 0.0 > reports/hw01/raw/run_00_%%i.txt
)

echo.
echo All 40 runs complete!
pause