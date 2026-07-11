# PetColinas Instagram Automation

Sistema de automatizacion para publicar contenido diario en Instagram de PetColinas usando solo GitHub Actions, OpenAI y Meta Graph API.

## Que hace

- Corre todos los dias a las 9:00 AM hora Republica Dominicana (UTC-4).
- OpenAI genera la estrategia, caption y prompt visual.
- OpenAI Images genera la imagen del post.
- Pillow normaliza la imagen a `1080x1080` y superpone el logo.
- GitHub Actions guarda `post_del_dia.jpg` y `caption.txt` en el repo.
- Meta Graph API publica el post en Instagram.

## Secrets necesarios

Configurar en GitHub: `Settings -> Secrets and variables -> Actions -> Secrets`.

- `OPENAI_API_KEY`
- `IG_ACCESS_TOKEN`
- `INSTAGRAM_ACCOUNT_ID`

El workflow valida los 3 secrets como primer paso y falla rapido con un mensaje claro si falta alguno (sin imprimir sus valores).

## Variables opcionales de modelo

Configurar en GitHub: `Settings -> Secrets and variables -> Actions -> Variables` (no son secrets).

- `OPENAI_TEXT_MODEL` (default: `gpt-5.5`)
- `OPENAI_IMAGE_MODEL` (default: `gpt-image-2`)

Si el modelo configurado no existe o no esta autorizado para la cuenta, el script reintenta una vez con un modelo alternativo conocido (`gpt-4.1` para texto, `gpt-image-1` para imagen) y deja en el log cual modelo se uso al final.

## Issue automatico en fallos

Si cualquier paso del workflow falla, un paso final crea un Issue en el repo indicando que paso fallo y el link al run. Si ya existe un Issue abierto con el mismo titulo, comenta en ese Issue en vez de crear uno nuevo.

## Logo

Sube el logo manualmente en:

```text
assets/logo_petcolinas.png
```

Debe ser PNG con fondo transparente. El script lo redimensiona automaticamente a 150px de ancho.

## Horario

El workflow usa:

```yaml
cron: "0 13 * * *"
```

Eso equivale a 9:00 AM en Republica Dominicana (UTC-4), todos los dias, incluyendo martes.

## Prueba manual

En GitHub:

```text
Actions -> PetColinas - Contenido Diario Automatico -> Run workflow
```

## Notas importantes

- El repo debe ser publico para que Instagram pueda descargar `post_del_dia.jpg` desde `raw.githubusercontent.com`.
- La URL de la imagen que se envia a Instagram va pineada al SHA del commit (`raw.githubusercontent.com/<repo>/<SHA>/post_del_dia.jpg`), asi que no depende de la cache del CDN de la rama `main`.
- El token de Instagram de Meta normalmente vence y debe renovarse segun la configuracion de Meta.
- OpenAI Images puede requerir verificacion de organizacion y genera costos por uso.
