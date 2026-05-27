import os
import json
import time
import pika
from PIL import Image

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")


def resize_image(img: Image.Image, width: int, height: int, mode: str) -> Image.Image:
    if mode == "stretch":
        return img.resize((width, height), Image.LANCZOS)

    if mode == "fit":
        img.thumbnail((width, height), Image.LANCZOS)
        # вставляем в холст нужного размера с чёрными полями
        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        offset = ((width - img.width) // 2, (height - img.height) // 2)
        canvas.paste(img, offset)
        return canvas

    if mode == "fill":
        src_ratio = img.width / img.height
        dst_ratio = width / height
        if src_ratio > dst_ratio:
            # обрезаем по ширине
            new_w = int(img.height * dst_ratio)
            left = (img.width - new_w) // 2
            img = img.crop((left, 0, left + new_w, img.height))
        else:
            # обрезаем по высоте
            new_h = int(img.width / dst_ratio)
            top = (img.height - new_h) // 2
            img = img.crop((0, top, img.width, top + new_h))
        return img.resize((width, height), Image.LANCZOS)

    raise ValueError(f"Неизвестный режим ресайза: {mode}")


def process_image(task: dict):
    original_path = task["original_path"]
    result_path = task["result_path"]
    resize_mode = task.get("resize_mode", "stretch")
    width = task.get("width", 800)
    height = task.get("height", 800)

    img = Image.open(original_path)
    img = resize_image(img, width, height, resize_mode)
    img = img.convert("RGB")
    img.save(result_path, "JPEG", quality=85)

    print(f"[worker] готово ({resize_mode} {width}x{height}): {result_path}")


def on_message(channel, method, properties, body):
    task = json.loads(body)
    print(f"[worker] взял задачу: {task['task_id']}")

    try:
        process_image(task)
        channel.basic_ack(delivery_tag=method.delivery_tag)  # подтверждаем что задача выполнена
    except Exception as e:
        print(f"[worker] ошибка: {e}")
        error_path = task["result_path"].replace("_result.jpg", "_error.txt")
        with open(error_path, "w") as f:
            f.write(str(e))
        channel.basic_ack(delivery_tag=method.delivery_tag)  # не возвращаем в очередь


def main():
    # ждём пока RabbitMQ поднимется
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            break
        except Exception:
            print("[worker] жду RabbitMQ...")
            time.sleep(3)

    channel = connection.channel()
    channel.queue_declare(queue="image_tasks", durable=True)
    channel.basic_qos(prefetch_count=1)  # брать по одной задаче за раз
    channel.basic_consume(queue="image_tasks", on_message_callback=on_message)

    print("[worker] слушаю очередь...")
    channel.start_consuming()


if __name__ == "__main__":
    main()
