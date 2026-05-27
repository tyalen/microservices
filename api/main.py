import os
import uuid as uuid_lib
import json
import time
import pika
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from typing import List, Literal

STORAGE_PATH = "/storage"
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")

ResizeMode = Literal["stretch", "fit", "fill"]

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}  # допустимые типы файлов

rabbitmq_connection = None
rabbitmq_channel = None


@asynccontextmanager
async def lifespan(app):
    # при старте — ждём RabbitMQ и создаём одно соединение на всё время работы
    global rabbitmq_connection, rabbitmq_channel
    while True:
        try:
            rabbitmq_connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            rabbitmq_channel = rabbitmq_connection.channel()
            rabbitmq_channel.queue_declare(queue="image_tasks", durable=True)
            print("[api] подключился к RabbitMQ")
            break
        except Exception:
            print("[api] жду RabbitMQ...")
            time.sleep(3)
    yield
    # при остановке — закрываем соединение
    rabbitmq_connection.close()


app = FastAPI(lifespan=lifespan)


@app.post("/upload")
async def upload_images(
    files: List[UploadFile] = File(...),
    resize_mode: ResizeMode = Form("stretch"),
    width: int = Form(800),
    height: int = Form(800),
):
    # проверяем тип каждого файла до обработки
    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename}: недопустимый тип файла. Разрешены: JPEG, PNG, GIF, WEBP"
            )

    task_ids = []

    for file in files:
        # генерируем уникальный id для каждой картинки
        task_id = str(uuid_lib.uuid4())
        original_path = f"{STORAGE_PATH}/{task_id}_original.jpg"

        # сохраняем оригинал
        content = await file.read()
        with open(original_path, "wb") as f:
            f.write(content)

        # кладём задачу в очередь
        task = {
            "task_id": task_id,
            "original_path": original_path,
            "result_path": f"{STORAGE_PATH}/{task_id}_result.jpg",
            "resize_mode": resize_mode,
            "width": width,
            "height": height,
        }
        rabbitmq_channel.basic_publish(
            exchange="",
            routing_key="image_tasks",
            body=json.dumps(task),
            properties=pika.BasicProperties(delivery_mode=2),  # задача не потеряется при рестарте
        )

        task_ids.append(task_id)

    return {
        "message": f"Принято {len(files)} файлов, задачи созданы",
        "task_ids": task_ids,
        "resize_mode": resize_mode,
        "target_size": {"width": width, "height": height},
    }


@app.get("/status/{task_id}")
def get_status(task_id: str):
    # проверяем что task_id это валидный UUID, а не что-то вроде ../../etc/passwd
    try:
        uuid_lib.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный task_id")

    result_path = f"{STORAGE_PATH}/{task_id}_result.jpg"
    error_path = f"{STORAGE_PATH}/{task_id}_error.txt"

    if os.path.exists(result_path):
        return {"task_id": task_id, "status": "done", "result": result_path}
    elif os.path.exists(error_path):
        with open(error_path) as f:
            return {"task_id": task_id, "status": "error", "reason": f.read()}
    else:
        return {"task_id": task_id, "status": "processing"}
