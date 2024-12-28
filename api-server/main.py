from fastapi import FastAPI,Request,WebSocket
import json
import boto3
import config
from utils import generate_uuid_slug
import uvicorn
import config

app = FastAPI()




# Initialize AWS clients
ecs_client = boto3.client("ecs",
                                      region_name="ap-south-1",
                                      aws_access_key_id=config.aws_access_key_id,
                                      aws_secret_access_key=config.aws_secret_access_key)

@app.post("/trigger-build")
async def trigger_build(req : Request):
    data = await req.json()
    project_id = data.get("project_id") if data.get("project_id") else generate_uuid_slug()
    git_url = data.get("git_url")
    try:
        response = ecs_client.run_task(
            cluster=config.cluster_name,  # Your ECS cluster name
            taskDefinition=config.task_definition_family,  # Your task definition name
            launchType='FARGATE',
            networkConfiguration={
                'awsvpcConfiguration': {
                    'subnets':config.subnets   # Your subnet IDs
                    ,
                    'securityGroups': config.security_groups,  # Your security group IDs
                    'assignPublicIp': 'ENABLED'  # or 'DISABLED' based on your needs
                }
            },
            overrides={
                'containerOverrides': [
                    {
                        'name': 'builder-image',  # Container name in task definition
                        'environment': [
                            {
                                'name': 'PROJECT_ID',
                                'value': project_id
                            },
                            {
                                'name': 'GIT_REPOSITRY_URL',
                                'value': git_url
                            }
                        ]
                    }
                ]
            }
        )
        print(response)
        return {"message": "Task started", "taskArn": response['tasks'][0]['taskArn'] , "project_id": project_id}
    except Exception as e:
        return {"error": str(e)}




# web-socket using socket io

import socketio
from redis import Redis
import time
import redis

sio = socketio.Server(cors_allowed_origins='*')
app = socketio.WSGIApp(sio)
    
@sio.on('subscribe')
def subscribe(sid, channel):
    sio.enter_room(sid, channel)
    sio.emit('message', {'data': 'Connected to channel ' + channel}, room=sid)
    print("Connected to channel ", channel)

async def init_redis_subscribe():
   redis_client = redis.from_url(config.redis_url)
   redis_pubsub = redis_client.pubsub()
   await redis_pubsub.subscribe('app_logs:*')

   for message in redis_pubsub.listen():
       if message['type'] == 'pmessage':
           sio.emit('message', {'data': message['data'].decode('utf-8')}, room=message['channel'])

# //socket using fastapi
active_connections = {}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    
    try:
        # Store the connection
        if client_id not in active_connections:
            active_connections[client_id] = set()
        active_connections[client_id].add(websocket)
        
        # Handle subscription messages
        async for message in websocket:
            data = json.loads(message)
            if data['action'] == 'subscribe':
                channel = data['channel']
                # Send confirmation
                await websocket.send_json({
                    "type": "system",
                    "message": f"Joined {channel}"
                })

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup on disconnect
        if client_id in active_connections:
            active_connections[client_id].remove(websocket)

# Redis subscription handler
@app.on_event("startup")
async def startup_event():
    # Connect to Redis
    redis_client = redis.from_url(config.redis_url)
    pubsub = redis_client.pubsub()
    
    async def redis_listener():
        await pubsub.psubscribe('app_logs:*')
        
        async for message in pubsub.listen():
            if message['type'] == 'pmessage':
                # Broadcast to all connected clients for this channel
                channel = message['channel']
                for connections in active_connections.values():
                    for websocket in connections:
                        try:
                            await websocket.send_json({
                                "channel": channel,
                                "data": message['data']
                            })
                        except Exception as e:
                            print(f"Error sending to client: {e}")
    
    # Start Redis listener
    import asyncio
    asyncio.create_task(redis_listener())
if __name__ == "__main__":
 uvicorn.run(app, host="localhost", port=8000)