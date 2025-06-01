@echo off
echo Running HomieProxy tests in Docker container...
echo.

docker run --rm --network host ^
  -v "%cd%":/workspace ^
  -w /workspace ^
  -e PROXY_HOST=localhost ^
  -e PROXY_PORT=8123 ^
  -e PROXY_NAME=external-only-route ^
  -e PROXY_TOKEN=0061b276-ebab-4892-8c7b-13812084f5e9 ^
  -e PYTHONIOENCODING=utf-8 ^
  -e LANG=C.UTF-8 ^
  -e LC_ALL=C.UTF-8 ^
  python:3.11-slim bash -c "pip install requests && python tests/run_all_tests.py --force --concurrent"

echo.
echo Test run completed!
pause 