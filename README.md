# Image Processing Service

Сервис асинхронной обработки изображений. Принимает картинки, изменяет размер и сохраняет результат.

## Запуск

```bash
docker compose up --build
```

Остановить:
```bash
docker compose down
```

Масштабировать воркеры или API:
```bash
docker compose up --scale worker=3 --scale api=2
```

---

## Загрузка изображений

```bash
curl.exe -X POST http://localhost/upload \
  -F "files=@C:/path/to/image.jpg" \
  -F "resize_mode=stretch" \
  -F "width=800" \
  -F "height=800"
```

Несколько файлов сразу:
```bash
curl.exe -X POST http://localhost/upload \
  -F "files=@C:/path/to/image1.jpg" \
  -F "files=@C:/path/to/image2.jpg" \
  -F "files=@C:/path/to/image3.png" \
  -F "resize_mode=fit" \
  -F "width=1920" \
  -F "height=1080"
```

### Режимы ресайза (`resize_mode`)

| Режим | Описание |
|-------|----------|
| `stretch` | Растянуть до нужного размера, пропорции не сохраняются |
| `fit` | Вписать в размер с чёрными полями, пропорции сохраняются |
| `fill` | Обрезать и заполнить весь кадр, пропорции сохраняются |

---

## Проверка статуса задачи

```bash
curl.exe http://localhost/status/{task_id}
```

Ответ пока обрабатывается:
```json
{"task_id": "uuid", "status": "processing"}
```

Ответ когда готово:
```json
{"task_id": "uuid", "status": "done", "result": "/storage/uuid_result.jpg"}
```

Ответ если ошибка при обработке:
```json
{"task_id": "uuid", "status": "error", "reason": "cannot identify image file"}
```

---

## Веб-интерфейс RabbitMQ

Открыть в браузере: [http://localhost:15672](http://localhost:15672)

Логин: `guest` / Пароль: `guest`
