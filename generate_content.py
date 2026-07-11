"""
Orquestador automatico de contenido para PetColinas.

Genera dos archivos en el directorio actual:
  post_del_dia.jpg  -> imagen 1080x1080 JPEG con logo de PetColinas
  caption.txt       -> caption listo para Instagram

Variable de entorno requerida:
  OPENAI_API_KEY  -> API key de OpenAI

Variables de entorno opcionales:
  OPENAI_TEXT_MODEL   -> modelo de texto (default: gpt-5.5, fallback: gpt-4.1)
  OPENAI_IMAGE_MODEL  -> modelo de imagen (default: gpt-image-2, fallback: gpt-image-1)
"""

import base64
import datetime
import json
import os
import re
import sys
from io import BytesIO

from openai import OpenAI, OpenAIError
from PIL import Image


client = None

TEXT_MODEL_DEFAULT = "gpt-5.5"
TEXT_MODEL_FALLBACK = "gpt-4.1"
IMAGE_MODEL_DEFAULT = "gpt-image-2"
IMAGE_MODEL_FALLBACK = "gpt-image-1"

PETCOLINAS = """
EMPRESA: PetColinas - Veterinaria y Peluqueria Canina
UBICACION: Plaza Las Colinas, Av. Prolongacion 27 de Febrero, Santo Domingo Oeste, RD
WHATSAPP: 809-752-6806 | INSTAGRAM: @petcolinas
HORARIO: Todos los dias

SERVICIOS Y PRECIOS:
  Grooming -> Bano cachorro RD$699 | pequeno RD$799 | mediano RD$949 | grande RD$1,149
              Corte higienico RD$490 | completo RD$749 | bano medicado RD$950
              Bano pequeno con linea RD$999
  Veterinaria -> Consulta RD$1,500 | Vacuna quintuple RD$1,200 | Rabia RD$1,500
                 Giardia RD$1,450 | Bordetella RD$1,400 | Albendazol RD$300
  Membresias -> Basica RD$2,800/mes: 4 banos + turno prioritario + 10% OFF farmacia
                Plus RD$4,200/mes: 4 banos + 1 corte + turno VIP + 15% OFF + consulta gratis

COLORES DE MARCA: Verde oscuro #1a6b3a | Naranja #d45f1e | Dorado #c9a227

ESTILO: Calido, dominicano, cercano. Frases como "peludito", "nube de algodon",
  "bajo a perro", "tu peludo merece lo mejor". Nunca corporativo ni frio.

HASHTAGS: #PetColinas #GroomingRD #VeterinariaRD #MascotasRD #PerrosRD
          #SantoDomingoOeste #BanoPerros #PeluqueriaCanina #MascotasFelices #CuidaTuMascota
"""

CONTENT_TYPES = ["grooming", "veterinaria", "membresia", "educativo", "urgencia", "antes_despues"]

DOG_BREEDS = [
    "Golden Retriever", "Labrador Retriever", "Poodle", "Shih Tzu",
    "Maltese", "French Bulldog", "Bichon Frise", "Cocker Spaniel",
    "Schnauzer", "Yorkshire Terrier", "Havanese", "Pomeranian",
]

WEEKDAYS_ES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Error: falta la variable de entorno {name}")
        sys.exit(1)
    return value


def actionable_openai_error(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if status == 401:
        return (
            "Error OpenAI (401): API key invalida o revocada. "
            "Renueva la API key en platform.openai.com/api-keys y actualiza el secret OPENAI_API_KEY en GitHub."
        )
    if status == 404:
        return (
            "Error OpenAI (404): modelo no disponible para esta cuenta. "
            "Configura OPENAI_TEXT_MODEL / OPENAI_IMAGE_MODEL con un modelo valido en las variables del repositorio."
        )
    if status == 429:
        return (
            "Error OpenAI (429): cuota o limite de uso excedido. "
            "Revisa el plan y la facturacion en platform.openai.com/settings/organization/billing."
        )
    return f"Error OpenAI: {exc}"


def is_model_unavailable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 404:
        return True
    code = str(getattr(exc, "code", "") or "")
    if code == "model_not_found":
        return True
    message = str(exc).lower()
    return "model" in message and ("not found" in message or "does not exist" in message)


def call_with_model_fallback(kind: str, primary: str, fallback: str, fn):
    try:
        result = fn(primary)
        print(f"  Modelo de {kind} usado: {primary}")
        return result
    except OpenAIError as exc:
        if primary == fallback or not is_model_unavailable(exc):
            raise
        print(f"  Aviso: modelo de {kind} '{primary}' no disponible. Reintentando con '{fallback}'...")
        result = fn(fallback)
        print(f"  Modelo de {kind} usado: {fallback}")
        return result


def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"OpenAI no retorno JSON valido:\n{text}") from None
        return json.loads(match.group())


def openai_generate_content(model: str) -> dict:
    if client is None:
        raise RuntimeError("Cliente OpenAI no inicializado")

    today = datetime.date.today()
    weekday = WEEKDAYS_ES[today.weekday()]
    breed = DOG_BREEDS[today.timetuple().tm_yday % len(DOG_BREEDS)]

    prompt = f"""Hoy es {weekday} {today.strftime('%d/%m/%Y')}.

{PETCOLINAS}

Tipos de post: {', '.join(CONTENT_TYPES)}
Raza del dia para la imagen: {breed}

Crea el contenido completo del post de Instagram de hoy.
Responde UNICAMENTE con JSON valido, sin markdown ni texto extra.

Esquema requerido:
{{
  "tipo": "<uno de los tipos listados>",
  "tema": "<tema especifico, max 25 palabras>",
  "prompt_imagen": "<prompt HIPER REALISTA en INGLES para {breed}. Escena concreta: el perro sentado quieto mirando a camara, recien baniado y arreglado, pelo limpio y brillante, salon de grooming con pared verde oscura, iluminacion de ventana lateral suave. Camara: Sony A7 85mm f2.0, bokeh suave. SOLO UN perro, 4 patas visibles, anatomia perfecta, sin texto en la imagen. Max 80 palabras.>",
  "caption": "<caption completo listo para Instagram: 1) linea gancho con emoji, 2) cuerpo 2-3 oraciones tono dominicano calido, 3) CTA claro, 4) contacto 809-752-6806 y Plaza Las Colinas, 5) 10-12 hashtags. Max 2200 caracteres.>"
}}"""

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "Eres el estratega y creador de contenido oficial de PetColinas en Instagram. "
                    "Conoces el mercado dominicano, escribes captions calidos y cercanos, y generas "
                    "prompts fotograficos realistas que convierten."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        text={"format": {"type": "json_object"}},
    )

    data = extract_json(response.output_text.strip())
    required = {"tipo", "tema", "prompt_imagen", "caption"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"OpenAI retorno JSON incompleto. Faltan: {sorted(missing)}")
    if data["tipo"] not in CONTENT_TYPES:
        raise ValueError(f"Tipo de contenido invalido: {data['tipo']}")
    return data


def generate_image(image_prompt: str, model: str) -> bytes:
    if client is None:
        raise RuntimeError("Cliente OpenAI no inicializado")

    photo_prefix = (
        "Hyperrealistic professional pet photography, Sony A7III, 85mm portrait lens, "
        "f/2.0 aperture, natural window light, shallow depth of field, detailed clean fur, "
        "real grooming salon, no text, no watermark, no extra animals, no distorted anatomy. "
    )
    full_prompt = (photo_prefix + image_prompt)[:32000]

    print(f"  Generando imagen con OpenAI Images ({model})...")
    result = client.images.generate(
        model=model,
        prompt=full_prompt,
        size="1024x1024",
        quality="high",
    )

    image_base64 = result.data[0].b64_json
    if not image_base64:
        raise ValueError("OpenAI Images no retorno b64_json")

    img = Image.open(BytesIO(base64.b64decode(image_base64))).convert("RGB")
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
    img = img.resize((1080, 1080), Image.LANCZOS)

    logo_path = "assets/logo_petcolinas.png"
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo_w = 150
            ratio = logo_w / logo.width
            logo_h = int(logo.height * ratio)
            logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
            x = 1080 - logo_w - 20
            y = 20
            img.paste(logo, (x, y), logo)
            print("  Logo superpuesto en esquina superior derecha")
        except Exception as exc:
            print(f"  Aviso: no se pudo agregar el logo ({exc})")
    else:
        print("  Aviso: assets/logo_petcolinas.png no encontrado")

    output = BytesIO()
    img.save(output, format="JPEG", quality=95, optimize=True)
    return output.getvalue()


def main() -> None:
    global client
    client = OpenAI(api_key=require_env("OPENAI_API_KEY"))
    text_model = os.getenv("OPENAI_TEXT_MODEL") or TEXT_MODEL_DEFAULT
    image_model = os.getenv("OPENAI_IMAGE_MODEL") or IMAGE_MODEL_DEFAULT
    today = datetime.date.today()

    print(f"\n{'=' * 50}")
    print(f"  ORQUESTADOR PETCOLINAS - {today.strftime('%d/%m/%Y')}")
    print(f"{'=' * 50}\n")

    try:
        print("[OpenAI] Generando estrategia, tema y caption...")
        content = call_with_model_fallback(
            "texto", text_model, TEXT_MODEL_FALLBACK, openai_generate_content
        )
        print(f"  Tipo   : {content['tipo']}")
        print(f"  Tema   : {content['tema']}")
        print(f"  Caption: {content['caption'][:80]}...")

        print("\n[OpenAI Images] Generando imagen hiper-realista 1080x1080...")
        image_bytes = call_with_model_fallback(
            "imagen",
            image_model,
            IMAGE_MODEL_FALLBACK,
            lambda model: generate_image(content["prompt_imagen"], model),
        )
    except OpenAIError as exc:
        print(f"\n{actionable_openai_error(exc)}")
        sys.exit(1)
    except ValueError as exc:
        print(f"\nError: OpenAI devolvio una respuesta invalida: {exc}")
        sys.exit(1)

    with open("post_del_dia.jpg", "wb") as file:
        file.write(image_bytes)
    print(f"  Imagen guardada: post_del_dia.jpg ({len(image_bytes):,} bytes)")

    with open("caption.txt", "w", encoding="utf-8") as file:
        file.write(content["caption"])
    print("  Caption guardado: caption.txt")

    print("\nContenido listo. El workflow publicara en Instagram.")


if __name__ == "__main__":
    main()
