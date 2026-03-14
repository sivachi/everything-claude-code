#!/bin/bash

# limitless_audio_fetch.py を再帰的に実行するラッパースクリプト
# スクリプトが異常終了または失敗した場合、少し待機してから再実行します。
# 正常終了（全データ取得完了）するまでループします。

SCRIPT_DIR=$(cd $(dirname $0); pwd)
PYTHON_SCRIPT="$SCRIPT_DIR/limitless_audio_fetch.py"

echo "Running limitless_audio_fetch.py recursively until success..."

while true; do
    echo "--------------------------------------------------"
    echo "Starting execution at $(date)"
    
    # Pythonスクリプトを実行
    # python3が失敗（exit code != 0）した場合、ループが継続します
    python3 "$PYTHON_SCRIPT"
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "Execution finished successfully."
        break
    else
        echo "Execution failed or interrupted (Exit code: $EXIT_CODE)."
        echo "Restarting in 10 seconds..."
        sleep 10
    fi
done

echo "All tasks completed."
