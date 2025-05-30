import subprocess
import time
import signal
import sys
import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()

def start_processes():
    processes = []
    
    # 環境変数から設定を取得
    api_host = os.getenv('API_HOST', '0.0.0.0')
    api_port = os.getenv('API_PORT', '8000')
    worker_id = os.getenv('WORKER_ID', 'worker-1')
    
    try:
        # FastAPIサーバーを起動
        print("FastAPIサーバーを起動中...")
        print(f"  - Host: {api_host}")
        print(f"  - Port: {api_port}")
        api_process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", "main:app", 
            "--host", api_host, "--port", api_port, "--reload"
        ])
        processes.append(api_process)
        
        time.sleep(2)  # APIサーバーの起動を待つ
        
        # ワーカーを起動
        print("注文処理ワーカーを起動中...")
        print(f"  - Worker ID: {worker_id}")
        worker_process = subprocess.Popen([
            sys.executable, "worker.py", worker_id
        ])
        processes.append(worker_process)
        
        print("\n=== Redis Stream Order Processing System ===")
        print(f"API: http://localhost:{api_port}")
        print(f"Docs: http://localhost:{api_port}/docs")
        print(f"Redis: {os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}")
        print("\nCtrl+C で停止")
        
        # プロセスが終了するまで待機
        for process in processes:
            process.wait()
            
    except KeyboardInterrupt:
        print("\n\nシステムを停止中...")
        for process in processes:
            process.terminate()
        
        time.sleep(1)
        
        for process in processes:
            if process.poll() is None:
                process.kill()
        
        print("停止完了")

if __name__ == "__main__":
    start_processes()
