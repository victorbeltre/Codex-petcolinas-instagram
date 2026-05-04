"""
Orquestador automatico de contenido para PetColinas.

Genera dos archivos en el directorio actual:
  post_del_dia.jpg  -> imagen 1080x1080 JPEG con logo de PetColinas
  caption.txt       -> caption listo para Instagram

Variable de entorno requerida:
  OPENAI_API_KEY  -> API key de OpenAI
"""

import base64
import datetime
import json
import os
import re
import sys
from io import BytesIO

from openai import OpenAI
from PIL import Image


client = None

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


def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"OpenAI no retorno JSON valido:\n{text}") from None
        return json.loads(match.group())


def openai_generate_content() -> dict:
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
