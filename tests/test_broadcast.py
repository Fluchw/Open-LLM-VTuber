import asyncio
import traceback
import websockets
import json
import logging
from datetime import datetime
import os

# 创建logs目录（如果不存在）
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)

# 设置日志格式
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 创建文件处理器，使用时间戳命名日志文件
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
file_handler = logging.FileHandler(
    os.path.join(log_dir, f'broadcast_test_{timestamp}.log'),
    encoding='utf-8'
)
file_handler.setFormatter(log_format)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_format)

# 配置根日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 消息队列（共享消息）
message_queue = asyncio.Queue()

async def websocket_client():
    """监听 WebSocket 消息，并将消息放入队列"""
    uri = "ws://localhost:12393/client-ws"
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("WebSocket客户端连接已建立")
            while True:
                message = await websocket.recv()
                msg = json.loads(message)
                if msg['type'] != 'audio':
                    logger.info(f"客户端收到消息: {msg}")

                # 放入队列供 broadcast_client 处理
                    await message_queue.put(msg)
    except Exception as e:
        logger.error(f"WebSocket客户端错误: {e}\n{traceback.format_exc()}")

async def broadcast_client():
    """模拟一个广播消息的WebSocket客户端"""
    uri = "ws://localhost:12393/broadcast-ws"
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("广播WebSocket连接已建立")
            msg_list = ['你好啊', '你在做什么呢', '你中午吃了什么', '你要和我去游乐园玩吗']
            i = 0
            while True:

                message = {
                    "type": "text-input",
                    "text": msg_list[i % len(msg_list)]
                }
                # 发送消息
                await websocket.send(json.dumps(message))
                # 确认发送,必须有,不如会出bug,不知道为啥
                await websocket.send(json.dumps(message))
                logger.info(f"广播发送: {message}")
                # 接收状态回执
                response = await websocket.recv()
                logger.info(f"广播状态: {response}")

                # {'type': 'control', 'text': 'conversation-chain-end'}
                while True:
                    if message_queue.empty():
                        logger.info(f"广播端队列空")
                        await asyncio.sleep(1)
                        continue
                    received_message = await message_queue.get()  # 从队列获取消息
                    logger.info(f"广播端收到: {received_message}")

                    if received_message['type'] == 'control' and received_message['text'] == 'conversation-chain-end':
                        await asyncio.sleep(5)
                        break
                # await asyncio.sleep(30)  # 等待15秒发送下一条
                i += 1
    except Exception as e:
        logger.error(f"WebSocket客户端错误: {e}\n{traceback.format_exc()}")

async def main():
    """主函数：同时运行接收客户端和广播客户端"""
    try:
        await asyncio.gather(
            websocket_client(),
            broadcast_client()
        )
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"运行时出错: {e}")

if __name__ == "__main__":
    try:
        logger.info("=== 开始测试广播功能 ===")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"运行时出错: {e}")
    finally:
        logger.info("=== 测试结束 ===")
