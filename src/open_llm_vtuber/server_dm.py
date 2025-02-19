import os
import shutil
import asyncio

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes_dm import create_routes
from .service_context import ServiceContext
from .config_manager.utils import Config


class CustomStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if path.endswith(".js"):
            response.headers["Content-Type"] = "application/javascript"
        return response


class WebSocketServer:
    def __init__(self, config: Config):
        self.app = FastAPI()
        self.connected_clients = []
        self.message_queue = asyncio.Queue()  # 新增消息队列

        # Add CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Load configurations and initialize the default context cache
        default_context_cache = ServiceContext()
        default_context_cache.load_from_config(config)

        # Include routes
        self.app.include_router(
            create_routes(
                default_context_cache=default_context_cache, 
                connected_clients=self.connected_clients,
                message_queue=self.message_queue
            )
        )

        # Mount static files
        self.app.mount(
            "/live2d-models",
            StaticFiles(directory="live2d-models"),
            name="live2d-models",
        )
        self.app.mount(
            "/bg",
            StaticFiles(directory="backgrounds"),
            name="backgrounds",
        )
        self.app.mount(
            "/", CustomStaticFiles(directory="./frontend", html=True), name="frontend"
        )

    def run(self):
        pass

    @staticmethod
    def clean_cache():
        """Clean the cache directory by removing and recreating it."""
        cache_dir = "./cache"
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            os.makedirs(cache_dir)
