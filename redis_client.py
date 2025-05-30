import redis
import json
import os
from typing import List, Dict, Any, Optional
from models import Order, OrderStatus
import time

class RedisStreamClient:
    def __init__(self, host=None, port=None, db=0):
        # 環境変数からRedis接続情報を取得（load_dotenv()は呼び出し元で実行済み）
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port or int(os.getenv('REDIS_PORT', 6379))
        self.db = db
        
        self.redis = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)
        self.orders_stream = "orders:stream"
        self.consumer_group = "order_processors"
        
        # Redis接続テスト
        try:
            self.redis.ping()
            print(f"Redis接続成功: {self.host}:{self.port}")
        except redis.ConnectionError:
            print(f"Redis接続失敗: {self.host}:{self.port}")
            raise
        
        # コンシューマーグループを作成（既に存在する場合はスキップ）
        try:
            self.redis.xgroup_create(
                self.orders_stream, 
                self.consumer_group, 
                id="0", 
                mkstream=True
            )
        except redis.exceptions.ResponseError:
            pass  # グループが既に存在する場合
    
    def add_order(self, order: Dict[str, Any]) -> str:
        """注文をStreamに追加"""
        order_data = {
            'customer_id': order['customer_id'],
            'product_id': order['product_id'],
            'quantity': str(order['quantity']),
            'price': str(order['price']),
            'status': OrderStatus.PENDING.value,
            'created_at': str(time.time())
        }
        
        message_id = self.redis.xadd(self.orders_stream, order_data)
        return message_id
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """特定の注文を取得"""
        try:
            result = self.redis.xrange(self.orders_stream, min=order_id, max=order_id)
            if result:
                message_id, fields = result[0]
                return Order(
                    id=message_id,
                    customer_id=fields['customer_id'],
                    product_id=fields['product_id'],
                    quantity=int(fields['quantity']),
                    price=float(fields['price']),
                    status=OrderStatus(fields['status']),
                    created_at=fields['created_at'],
                    processed_at=fields.get('processed_at')
                )
        except Exception:
            pass
        return None
    
    def get_orders(self, limit: int = 10) -> List[Order]:
        """最新の注文一覧を取得"""
        try:
            result = self.redis.xrevrange(self.orders_stream, count=limit)
            orders = []
            for message_id, fields in result:
                orders.append(Order(
                    id=message_id,
                    customer_id=fields['customer_id'],
                    product_id=fields['product_id'],
                    quantity=int(fields['quantity']),
                    price=float(fields['price']),
                    status=OrderStatus(fields['status']),
                    created_at=fields['created_at'],
                    processed_at=fields.get('processed_at')
                ))
            return orders
        except Exception:
            return []
    
    def read_pending_orders(self, consumer_name: str, count: int = 1):
        """コンシューマーグループから未処理の注文を読み取り"""
        try:
            result = self.redis.xreadgroup(
                self.consumer_group,
                consumer_name,
                {self.orders_stream: '>'},
                count=count,
                block=1000
            )
            
            if result:
                stream_name, messages = result[0]
                return messages
        except Exception:
            pass
        return []
    
    def acknowledge_order(self, message_id: str):
        """注文処理完了を通知"""
        self.redis.xack(self.orders_stream, self.consumer_group, message_id)
    
    def update_order_status(self, message_id: str, status: OrderStatus, processed_at: str = None):
        """
        注文ステータスを更新
        
        Redis Hashを使用してステータス情報を管理:
        - キー: order:status:{message_id}
        - フィールド: status, processed_at
        
        Redis Hashの特徴:
        - 一つのキー下に複数のフィールド-値ペアを格納
        - メモリ効率が良い（小さなハッシュの場合）
        - フィールド単位での操作が可能（HGET, HSET, HDEL等）
        - オブジェクトのような構造化データに最適
        """
        order_key = f"order:status:{message_id}"
        update_data = {'status': status.value}
        if processed_at:
            update_data['processed_at'] = processed_at
        
        # HSET: ハッシュに複数のフィールドを一度に設定
        self.redis.hset(order_key, mapping=update_data)
    
    def get_order_status_details(self, message_id: str) -> Dict[str, str]:
        """
        Redis Hashから注文ステータス詳細を取得
        
        使用するRedis Hashコマンド:
        - HGETALL: ハッシュの全フィールドと値を取得
        - HGET: 特定のフィールドの値を取得
        - HEXISTS: フィールドの存在確認
        """
        order_key = f"order:status:{message_id}"
        
        # 全フィールドを取得
        status_data = self.redis.hgetall(order_key)
        
        # 個別フィールドの取得例
        # status = self.redis.hget(order_key, 'status')
        # processed_at = self.redis.hget(order_key, 'processed_at')
        
        return status_data
    
    def delete_order_status(self, message_id: str):
        """Redis Hashキーを削除"""
        order_key = f"order:status:{message_id}"
        self.redis.delete(order_key)
    
    def get_all_order_statuses(self) -> Dict[str, Dict[str, str]]:
        """
        全ての注文ステータスを取得
        
        Redis Hashの検索パターン:
        - SCAN: キーのパターンマッチング
        - 大量のキーがある場合でもメモリ効率的
        """
        statuses = {}
        cursor = 0
        
        while True:
            cursor, keys = self.redis.scan(
                cursor=cursor, 
                match="order:status:*", 
                count=100
            )
            
            for key in keys:
                # キーから message_id を抽出
                message_id = key.replace("order:status:", "")
                statuses[message_id] = self.redis.hgetall(key)
            
            if cursor == 0:
                break
                
        return statuses
