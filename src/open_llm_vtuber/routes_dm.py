import json
import asyncio
import numpy as np
from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect
from loguru import logger
from .conversation import conversation_chain
from .service_context import ServiceContext
from .config_manager.utils import (
    scan_config_alts_directory,
    scan_bg_directory,
)
from .chat_history_manager import (
    create_new_history,
    store_message,
    modify_latest_message,
    get_history,
    delete_history,
    get_history_list,
)


def create_routes(default_context_cache: ServiceContext, connected_clients: list, message_queue: asyncio.Queue):
    router = APIRouter()
    
    class SharedState:
        def __init__(self):
            self.history_uid = None
            self.conversation_task = None
            self.data_buffer = np.array([])
            self.broadcast_websockets = set()  # 添加广播客户端集合
    
    state = SharedState()

    async def broadcast_message(message: str):
        """向所有连接的客户端广播消息"""
        disconnected = set()
        for ws in state.broadcast_websockets:
            try:
                logger.debug(f"Broadcasting message to client: {message}")
                await ws.send_text(message)
            except WebSocketDisconnect:
                disconnected.add(ws)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected.add(ws)
        
        # 移除断开连接的客户端
        state.broadcast_websockets.difference_update(disconnected)

    async def send_with_broadcast(websocket: WebSocket, message: str):
        """发送消息到主客户端并广播"""
        await websocket.send_text(message)
        await broadcast_message(message)

    # 添加这个包装函数
    def make_broadcast_send(websocket: WebSocket):
        """创建一个包装了send_with_broadcast的函数"""
        async def wrapped_send(message: str):
            await send_with_broadcast(websocket, message)
        return wrapped_send

    async def process_message(data: dict, websocket: WebSocket, session_service_context: ServiceContext):
        """处理单个消息的函数"""
        logger.debug(f"Processing message: {data}")
        
        # 如果还没有历史ID，创建一个新的
        if state.history_uid is None:
            state.history_uid = create_new_history(
                session_service_context.character_config.conf_uid
            )
            session_service_context.agent_engine.set_memory_from_history(
                conf_uid=session_service_context.character_config.conf_uid,
                history_uid=state.history_uid,
            )

        if data.get("type") == "fetch-history-list":
            histories = get_history_list(
                session_service_context.character_config.conf_uid
            )
            await send_with_broadcast(
                websocket, json.dumps({"type": "history-list", "histories": histories})
            )

        elif data.get("type") == "fetch-and-set-history":
            history_uid = data.get("history_uid")
            if history_uid:
                state.history_uid = history_uid
                session_service_context.agent_engine.set_memory_from_history(
                    conf_uid=session_service_context.character_config.conf_uid,
                    history_uid=history_uid,
                )
                messages = [
                    msg
                    for msg in get_history(
                        session_service_context.character_config.conf_uid,
                        history_uid,
                    )
                    if msg["role"] != "system"
                ]
                await send_with_broadcast(
                    websocket, json.dumps({"type": "history-data", "messages": messages})
                )

        elif data.get("type") == "create-new-history":
            state.history_uid = create_new_history(
                session_service_context.character_config.conf_uid
            )
            session_service_context.agent_engine.set_memory_from_history(
                conf_uid=session_service_context.character_config.conf_uid,
                history_uid=state.history_uid,
            )
            await send_with_broadcast(
                websocket,
                json.dumps(
                    {
                        "type": "new-history-created",
                        "history_uid": state.history_uid,
                    }
                )
            )

        elif data.get("type") == "delete-history":
            history_uid = data.get("history_uid")
            if history_uid:
                success = delete_history(
                    session_service_context.character_config.conf_uid,
                    history_uid,
                )
                await send_with_broadcast(
                    websocket,
                    json.dumps(
                        {
                            "type": "history-deleted",
                            "success": success,
                            "history_uid": history_uid,
                        }
                    )
                )
                if history_uid == state.history_uid:
                    state.history_uid = None

        elif data.get("type") == "interrupt-signal":
            if state.conversation_task is None:
                logger.warning(
                    "❌ Conversation task was NOT cancelled because there is no running conversation."
                )
            else:
                if not state.conversation_task.cancel():
                    logger.warning(
                        "❌ Conversation task was NOT cancelled for some reason."
                    )
                else:
                    logger.info(
                        "🛑 Conversation task was succesfully interrupted."
                    )
            heard_ai_response = data.get("text", "")

            try:
                session_service_context.agent_engine.handle_interrupt(
                    heard_ai_response
                )
            except Exception as e:
                logger.error(f"Error handling interrupt: {e}")

            if not modify_latest_message(
                conf_uid=session_service_context.character_config.conf_uid,
                history_uid=state.history_uid,
                role="ai",
                new_content=heard_ai_response,
            ):
                logger.warning("Failed to modify message.")
            logger.info(
                f"💾 Stored Paritial AI message: '''{heard_ai_response}'''"
            )

            store_message(
                conf_uid=session_service_context.character_config.conf_uid,
                history_uid=state.history_uid,
                role="system",
                content="[Interrupted by user]",
            )

        elif data.get("type") == "mic-audio-data":
            state.data_buffer = np.append(
                state.data_buffer,
                np.array(data.get("audio"), dtype=np.float32),
            )

        elif data.get("type") in [
            "mic-audio-end",
            "text-input",
            "ai-speak-signal",
        ]:
            await send_with_broadcast(
                websocket, json.dumps({"type": "full-text", "text": "Thinking..."})
            )

            if data.get("type") == "ai-speak-signal":
                user_input = ""
                await send_with_broadcast(
                    websocket,
                    json.dumps(
                        {
                            "type": "full-text",
                            "text": "AI wants to speak something...",
                        }
                    )
                )
            elif data.get("type") == "text-input":
                user_input = data.get("text")
            else:
                user_input = state.data_buffer

            state.data_buffer = np.array([])

            images = data.get("images")

            logger.debug(f"data: {data}")

            state.conversation_task = asyncio.create_task(
                conversation_chain(
                    user_input=user_input,
                    asr_engine=session_service_context.asr_engine,
                    tts_engine=session_service_context.tts_engine,
                    agent_engine=session_service_context.agent_engine,
                    live2d_model=session_service_context.live2d_model,
                    websocket_send=make_broadcast_send(websocket),  # 使用包装函数
                    translate_engine=session_service_context.translate_engine,
                    conf_uid=session_service_context.character_config.conf_uid,
                    history_uid=state.history_uid,
                    images=images,
                )
            )

        elif data.get("type") == "fetch-configs":
            config_files = scan_config_alts_directory(
                session_service_context.system_config.config_alts_dir
            )
            await send_with_broadcast(
                websocket, json.dumps({"type": "config-files", "configs": config_files})
            )
        elif data.get("type") == "switch-config":
            config_file_name: str = data.get("file")
            if config_file_name:
                await session_service_context.handle_config_switch(
                    websocket, config_file_name
                )
        elif data.get("type") == "fetch-backgrounds":
            bg_files = scan_bg_directory()
            await send_with_broadcast(
                websocket, json.dumps({"type": "background-files", "files": bg_files})
            )
        else:
            logger.info("Unknown data type received.")

    @router.websocket("/client-ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        session_service_context: ServiceContext = ServiceContext()
        session_service_context.load_cache(
            config=default_context_cache.config,
            system_config=default_context_cache.system_config,
            character_config=default_context_cache.character_config,
            live2d_model=default_context_cache.live2d_model,
            asr_engine=default_context_cache.asr_engine,
            tts_engine=default_context_cache.tts_engine,
            agent_engine=default_context_cache.agent_engine,
            translate_engine=default_context_cache.translate_engine,
        )

        await send_with_broadcast(
            websocket, json.dumps({"type": "full-text", "text": "Connection established"})
        )

        connected_clients.append(websocket)
        logger.info("Connection established")

        await send_with_broadcast(
            websocket,
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "model_info": session_service_context.live2d_model.model_info,
                    "conf_name": session_service_context.character_config.conf_name,
                    "conf_uid": session_service_context.character_config.conf_uid,
                }
            )
        )
        await send_with_broadcast(websocket, json.dumps({"type": "control", "text": "start-mic"}))

        async def message_processor():
            try:
                while True:
                    data = await message_queue.get()
                    try:
                        await process_message(data, websocket, session_service_context)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                    finally:
                        message_queue.task_done()
            except asyncio.CancelledError:
                logger.info("Message processor task cancelled")

        processor_task = asyncio.create_task(message_processor())

        try:
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)
                logger.debug(f"✨Received data from websocket: {data}")
                await message_queue.put(data)

        except WebSocketDisconnect:
            processor_task.cancel()
            connected_clients.remove(websocket)
            logger.info("Client disconnected")
        finally:
            await processor_task

    @router.websocket("/broadcast-ws")
    async def broadcast_websocket(websocket: WebSocket):
        """广播消息的WebSocket接口"""
        await websocket.accept()
        logger.info("Broadcast WebSocket connection established")
        
        # 添加到广播客户端集合
        state.broadcast_websockets.add(websocket)
        
        try:
            while True:
                # 接收广播消息
                message = await websocket.receive_text()
                data = json.loads(message)
                
                # 发送队列状态回执
                status = {
                    "queue_size": message_queue.qsize(),
                    "is_processing": state.conversation_task is not None,
                    "message": "Message queued for broadcast",
                    "status": "success"
                }
                await websocket.send_text(json.dumps(status))
                
                # 将消息放入队列
                await message_queue.put(data)
                
        except WebSocketDisconnect:
            logger.info("Broadcast WebSocket disconnected")
        except Exception as e:
            logger.error(f"Error in broadcast websocket: {e}")
        finally:
            state.broadcast_websockets.discard(websocket)
            await websocket.close()

    return router
