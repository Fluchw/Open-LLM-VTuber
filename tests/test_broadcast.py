import asyncio
import traceback
import websockets
import json
from loguru import logger
from datetime import datetime
import os

# 创建logs目录（如果不存在）
# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)

# 消息队列（共享消息）
# Message queue (shared messages)
# message_queue = asyncio.Queue()

async def broadcast_client():
    """
    模拟一个广播消息的WebSocket客户端
    Simulate a WebSocket client for broadcasting messages
    """
    uri = "ws://localhost:12393/broadcast-ws"
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("广播WebSocket连接已建立 | Broadcast WebSocket connection established")
            
            # 预定义消息列表
            # Predefined message list
            messages = [
                "你好啊",
                "你在做什么呢",
                "你中午吃了什么",
                "你要和我去游乐园玩吗"
            ]
            msg_index = 0
            # 存储最近一次音频的时长
            # Store the duration of the most recent audio
            last_duration_ms = 0

            async def send_next_message():
                """
                发送下一条消息
                Send the next message in queue
                """
                nonlocal msg_index
                if msg_index < len(messages):
                    message = {
                        "type": "text-input",
                        "text": messages[msg_index]
                    }
                    await websocket.send(json.dumps(message))
                    logger.info(f"广播发送消息 | Broadcasting message [{msg_index}]: {message}")
                    msg_index += 1

            # 发送第一条消息
            # Send the first message
            await send_next_message()

            while True:
                response = await websocket.recv()
                msg = json.loads(response)
                
                # 立即过滤掉大体积数据
                # Immediately filter out large data
                if "audio" in msg:
                    # 只保留必要的字段
                    # Keep only necessary fields
                    filtered_msg = {
                        "type": msg.get("type"),
                        "duration_ms": msg.get("duration_ms", 0),
                        "text": msg.get("text"),
                        "actions": msg.get("actions"),
                        "slice_length": msg.get("slice_length")
                    }
                    msg = filtered_msg
                    logger.info(f"收到音频消息 | Received audio message, duration: {msg['duration_ms']}ms")
                
                # 处理消息结束信号
                # Handle conversation end signal
                if msg.get("type") == "control" and msg.get("text") == "conversation-chain-end":
                    await send_next_message()

                logger.info(f"广播状态 | Broadcast status: {msg}")

    except Exception as e:
        logger.error(f"广播客户端错误 | Broadcast client error: {e}\n{traceback.format_exc()}")

async def main():
    """
    主函数：运行广播客户端
    Main function: Run broadcast client
    """
    try:
        await asyncio.gather(broadcast_client())
    except KeyboardInterrupt:
        logger.info("程序被用户中断 | Program interrupted by user")
    except Exception as e:
        logger.error(f"运行时出错 | Runtime error: {e}")

if __name__ == "__main__":
    try:
        logger.info("=== 开始测试广播功能 | Start testing broadcast function ===")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断 | Program interrupted by user")
    except Exception as e:
        logger.error(f"运行时出错 | Runtime error: {e}")
    finally:
        logger.info("=== 测试结束 | Test ended ===")
