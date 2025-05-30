from fastapi import FastAPI, HTTPException
from typing import List
import asyncio
import time
from models import OrderCreate, Order, OrderStatus
from redis_client import RedisStreamClient
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()

app = FastAPI(title="Redis Stream Order Processing API")
redis_client = RedisStreamClient()

@app.post("/orders", response_model=dict)
async def create_order(order: OrderCreate):
    """新しい注文を作成"""
    try:
        order_data = order.model_dump()
        message_id = redis_client.add_order(order_data)
        return {"message": "注文が作成されました", "order_id": message_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"注文作成エラー: {str(e)}")

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    """特定の注文を取得"""
    order = redis_client.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="注文が見つかりません")
    
    # ステータス更新情報があれば取得
    status_key = f"order:status:{order_id}"
    status_update = redis_client.redis.hgetall(status_key)
    if status_update:
        order.status = OrderStatus(status_update.get('status', order.status))
        order.processed_at = status_update.get('processed_at')
    
    return order

@app.get("/orders", response_model=List[Order])
async def get_orders(limit: int = 10):
    """注文一覧を取得"""
    orders = redis_client.get_orders(limit)
    
    # 各注文のステータス更新情報を取得
    for order in orders:
        status_key = f"order:status:{order.id}"
        status_update = redis_client.redis.hgetall(status_key)
        if status_update:
            order.status = OrderStatus(status_update.get('status', order.status))
            order.processed_at = status_update.get('processed_at')
    
    return orders

@app.get("/")
async def root():
    return {"message": "Redis Stream Order Processing API", "docs": "/docs"}

def main():
    print("Hello from redis-stream-learn!")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
