import os
import sys
import time

import requests


GRAPH_VERSION = "v19.0"


def graph_get(path: str, params: dict) -> dict:
    response = requests.get(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{path}",
        params=params,
        timeout=30,
    )
    try:
        data = response.json()
    except ValueError:
        response.raise_for_status()
        raise
    if response.status_code >= 400:
        print(f"Error Meta API GET {path}: {data}")
        sys.exit(1)
    return data


def graph_post(path: str, data: dict) -> dict:
    response = requests.post(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{path}",
        data=data,
        timeout=60,
    )
    try:
        payload = response.json()
    except ValueError:
        response.raise_for_status()
        raise
    if response.status_code >= 400:
        print(f"Error Meta API POST {path}: {payload}")
        sys.exit(1)
    return payload


def wait_until_ready(creation_id: str, token: str, timeout: int = 90) -> bool:
    waited = 0
    while waited < timeout:
        status_response = graph_get(
            creation_id,
            params={"fields": "status_code", "access_token": token},
        )
        status = status_response.get("status_code", "UNKNOWN")
        print(f"  Estado del container: {status}")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            print(f"  Error en container: {status_response}")
            return False
        time.sleep(5)
        waited += 5
    return False


def publish() -> None:
    token = os.getenv("IG_ACCESS_TOKEN")
    acc_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
    img_url = os.getenv("IMAGE_URL")
    caption = os.getenv("CAPTION")

    missing = [
        name
        for name, val in [
            ("IG_ACCESS_TOKEN", token),
            ("INSTAGRAM_ACCOUNT_ID", acc_id),
            ("IMAGE_URL", img_url),
            ("CAPTION", caption),
        ]
        if not val
    ]

    if missing:
        print(f"Error: faltan variables de entorno: {missing}")
        sys.exit(1)

    print(f"Creando container para: {img_url[:80]}...")

    container = graph_post(
        f"{acc_id}/media",
        data={"image_url": img_url, "caption": caption, "access_token": token},
    )

    if "error" in container:
        print(f"Error Meta API (crear container): {container['error'].get('message', container)}")
        sys.exit(1)

    if "id" not in container:
        print(f"Respuesta inesperada de Meta: {container}")
        sys.exit(1)

    creation_id = container["id"]
    print(f"Container creado con ID: {creation_id}")
    print("Esperando que Instagram procese la imagen...")

    if not wait_until_ready(creation_id, token):
        print("Error: Instagram no proceso la imagen a tiempo")
        sys.exit(1)

    published = graph_post(
        f"{acc_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
    )

    if "error" in published:
        print(f"Error Meta API (publicar): {published['error'].get('message', published)}")
        sys.exit(1)

    print(f"Post publicado en Instagram con exito! ID: {published.get('id')}")


if __name__ == "__main__":
    publish()
