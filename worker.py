import time
import random
from redis_client import RedisStreamClient
from models import OrderStatus
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()


class OrderProcessor:
    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.redis_client = RedisStreamClient()
    
    def process_order(self, message_id: str, fields: dict):
        """注文を処理"""
        print(f"[{self.worker_id}] 注文処理開始: {message_id}")
        print(f"  顧客ID: {fields['customer_id']}")
        print(f"  商品ID: {fields['product_id']}")
        print(f"  数量: {fields['quantity']}")
        print(f"  価格: {fields['price']}")
        
        # ステータスを処理中に更新
        self.redis_client.update_order_status(message_id, OrderStatus.PROCESSING)
        
        # 処理をシミュレート（1-5秒のランダムな処理時間）
        processing_time = random.uniform(1, 5)
        time.sleep(processing_time)
        
        # ランダムで成功/失敗を決定（90%の確率で成功）
        success = random.random() < 0.9
        
        if success:
            status = OrderStatus.COMPLETED
            print(f"[{self.worker_id}] 注文処理完了: {message_id}")
        else:
            status = OrderStatus.FAILED
            print(f"[{self.worker_id}] 注文処理失敗: {message_id}")
        
        # ステータスを更新
        processed_at = str(time.time())
        self.redis_client.update_order_status(message_id, status, processed_at)
        
        # 処理完了を通知
        self.redis_client.acknowledge_order(message_id)
    
    def run(self):
        """ワーカーを実行"""
        print(f"[{self.worker_id}] 注文処理ワーカーを開始...")
        
        while True:
            try:
                # 未処理の注文を読み取り
                messages = self.redis_client.read_pending_orders(self.worker_id)
                
                if messages:
                    for message_id, fields in messages:
                        self.process_order(message_id, fields)
                else:
                    # 新しい注文がない場合は少し待機
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                print(f"[{self.worker_id}] ワーカーを停止...")
                break
            except Exception as e:
                print(f"[{self.worker_id}] エラー: {e}")
                time.sleep(1)

if __name__ == "__main__":
    import sys
    worker_id = sys.argv[1] if len(sys.argv) > 1 else "worker-1"
    processor = OrderProcessor(worker_id)
    processor.run()
