from fastapi import WebSocket
from typing import Dict
import json

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        print(f"WebSocket 연결됨 - Client ID: {client_id}, 총 접속자: {len(self.active_connections)}")
        await self.broadcast_connection_count()

    async def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            print(f"WebSocket 연결 해제 - Client ID: {client_id}, 총 접속자: {len(self.active_connections)}")
            await self.broadcast_connection_count()

    async def broadcast(self, message: str):
        # 딕셔너리의 복사본 생성
        connections = dict(self.active_connections)
        disconnected_clients = []
        
        for client_id, connection in connections.items():
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"WebSocket 전송 오류 (Client ID: {client_id}): {e}")
                disconnected_clients.append(client_id)
        
        # 끊어진 연결 정리
        for client_id in disconnected_clients:
            await self.disconnect(client_id)

    async def broadcast_connection_count(self):
        message = json.dumps({
            "type": "connection_count",
            "count": len(self.active_connections)
        })
        await self.broadcast(message)