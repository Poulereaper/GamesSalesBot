# Games Sales Bot for Discord (named "GameRadar" on discord)
import asyncio
import json
from pathlib import Path
import aiohttp
import discord
from discord.ext import tasks, commands
import os
import datetime
import re

# ====== CONFIG ======
from dotenv import load_dotenv
# Load environment variables from .env file
# Make sure to create a .env file with DISCORD_TOKEN=your_token
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# ===== VAR ======
POLL_INTERVAL = 1 # Every (6h) in production Multiple of 6h
BEST_INTERVAL = 1 # Every day (Multiple of 24h)
POPULAR_REFRESH_INTERVAL = 60 * 60 * 48  # Every 2 days

SEEN_FILE = Path("seen.json") # Path to the seen file
GUILDS_FILE = Path("guilds.json")

MIN_DISCOUNT = 20 # min discount percent to notify by default
MAX_PRICE = 65.0 # max price in euros to notify by default
BEST_DISCOUNT = 30 # min discount percent for BestDeals by default
BEST_PRICE = 30.0 # max price in euros for BestDeals by default


# We will not get the messages if on flase but we will still track them
steamornot = True  # Whether to send Steam deals or not by default
cheapsharkornot = True  # Whether to send CheapShark deals or not by default
epicornot = True  # Whether to send Epic free games or not by default
bestdealsornot = False  # Whether to send BestDeals or not by default

steam_popular_appids = []
last_popular_refresh = 0

# ====== LANG ======

translations = {
    "steam_deal": {
        "fr": "🔥 **{title}** est en promo {discount}% — prix: {price}€ (Steam)\n{url}",
        "en": "🔥 **{title}** is on sale {discount}% — price: {price}€ (Steam)\n{url}",
        "es": "🔥 **{title}** está en oferta {discount}% — precio: {price}€ (Steam)\n{url}",
        "de": "🔥 **{title}** ist im Angebot {discount}% — Preis: {price}€ (Steam)\n{url}",
        "it": "🔥 **{title}** è in offerta {discount}% — prezzo: {price}€ (Steam)\n{url}"
    },
    "cheapshark_deal": {
        "fr": "💸 **{title}** — {savings}% de réduction — {price}€\n{url}",
        "en": "💸 **{title}** — {savings}% off — {price}€\n{url}",
        "es": "💸 **{title}** — {savings}% de descuento — {price}€\n{url}",
        "de": "💸 **{title}** — {savings}% Rabatt — {price}€\n{url}",
        "it": "💸 **{title}** — {savings}% di sconto — {price}€\n{url}"
    },
    "epic_free": {
        "fr": "🎁 **{title}** gratuit sur Epic Games Store !\nExpire le: {expiry}\n{url}",
        "en": "🎁 **{title}** free on Epic Games Store!\nExpires: {expiry}\n{url}",
        "es": "🎁 **{title}** gratis en Epic Games Store!\nExpira: {expiry}\n{url}",
        "de": "🎁 **{title}** kostenlos im Epic Games Store!\nEndet am: {expiry}\n{url}",
        "it": "🎁 **{title}** gratis su Epic Games Store!\nScade il: {expiry}\n{url}"
    },
    "help_text": {
         "fr": (
            "📖 **Commandes disponibles :**\n"
            "`$help` — Affiche cette aide\n"
            "`$lang fr/en` — Change la langue\n"
            "`$status` — Vérifie si le bot est en ligne\n"
            "`$setchannel` — Définit ce salon comme salon de notifications\n"
            "`$filters` — Affiche les filtres actuels ou les modifie (ex: `$filters min_discount=30 max_price=50 epic=on steam=off`)\n"
            "`bests` — Affiche les meilleures offres actuelles\n"
            "`free` — Affiche les jeux gratuits actuels\n"
        ),
        "en": (
            "📖 **Available commands:**\n"
            "`$help` — Show this help\n"
            "`$lang fr/en` — Change the language\n"
            "`$status` — Check if the bot is online\n"
            "`$setchannel` — Set this channel as the notification channel\n"
            "`$filters` — Show or edit filters (ex: `$filters min_discount=30 max_price=50 epic=on steam=off`)\n"
            "`bests` — Show current best deals\n"
            "`free` — Show current free games\n"
        ),
        "es": (
            "📖 **Comandos disponibles:**\n"
            "`$help` — Muestra esta ayuda\n"
            "`$lang es/fr/en/de/it` — Cambia el idioma\n"
            "`$status` — Verifica si el bot está en línea\n"
            "`$setchannel` — Establece este canal para notificaciones\n"
            "`$filters` — Muestra o edita filtros (ej: `$filters min_discount=30 max_price=50 epic=on steam=off`)\n"
            "`bests` — Muestra las mejores ofertas actuales\n"
            "`free` — Muestra los juegos gratuitos actuales\n"
        ),
        "de": (
            "📖 **Verfügbare Befehle:**\n"
            "`$help` — Zeigt diese Hilfe\n"
            "`$lang de/fr/en/es/it` — Sprache ändern\n"
            "`$status` — Prüft, ob der Bot online ist\n"
            "`$setchannel` — Setzt diesen Kanal für Benachrichtigungen\n"
            "`$filters` — Zeigt oder bearbeitet Filter (z.B.: `$filters min_discount=30 max_price=50 epic=on steam=off`)\n"
            "`bests` — Zeigt die besten aktuellen Angebote\n"
            "`free` — Zeigt aktuelle Gratis-Spiele\n"
        ),
        "it": (
            "📖 **Comandi disponibili:**\n"
            "`$help` — Mostra questo aiuto\n"
            "`$lang it/fr/en/es/de` — Cambia la lingua\n"
            "`$status` — Verifica se il bot è online\n"
            "`$setchannel` — Imposta questo canale per le notifiche\n"
            "`$filters` — Mostra o modifica i filtri (es: `$filters min_discount=30 max_price=50 epic=on steam=off`)\n"
            "`bests` — Mostra le migliori offerte attuali\n"
            "`free` — Mostra i giochi gratuiti attuali\n"
        )
    },
    "help_loops": {
         "fr": (
            "🔄 **Boucles automatiques suivies :**\n"
            "🔥 **Steam** — Vérifie les promos sur les jeux les plus populaires\n"
            "💸 **CheapShark** — Vérifie les grosses réductions sur plusieurs stores\n"
            "🎁 **Epic Games** — Vérifie les jeux gratuits de la semaine\n"
            "🌟 **BestDeals** — Résumé quotidien des meilleures offres"
        ),
        "en": (
            "🔄 **Automatic loops checked:**\n"
            "🔥 **Steam** — Tracks sales on the most popular games\n"
            "💸 **CheapShark** — Tracks major discounts across multiple stores\n"
            "🎁 **Epic Games** — Tracks weekly free games\n"
            "🌟 **BestDeals** — Daily summary of top deals"
        ),
        "es": (
            "🔄 **Bucles automáticos seguidos:**\n"
            "🔥 **Steam** — Comprueba ofertas en los juegos más populares\n"
            "💸 **CheapShark** — Comprueba grandes descuentos en varias tiendas\n"
            "🎁 **Epic Games** — Comprueba los juegos gratuitos de la semana\n"
            "🌟 **BestDeals** — Resumen diario de las mejores ofertas"
        ),
        "de": (
            "🔄 **Automatische Schleifen überwacht:**\n"
            "🔥 **Steam** — Überwacht Angebote der beliebtesten Spiele\n"
            "💸 **CheapShark** — Überwacht große Rabatte in mehreren Stores\n"
            "🎁 **Epic Games** — Überwacht wöchentliche Gratis-Spiele\n"
            "🌟 **BestDeals** — Tägliche Zusammenfassung der Top-Angebote"
        ),
        "it": (
            "🔄 **Cicli automatici seguiti:**\n"
            "🔥 **Steam** — Controlla le offerte sui giochi più popolari\n"
            "💸 **CheapShark** — Controlla i grandi sconti su vari store\n"
            "🎁 **Epic Games** — Controlla i giochi gratuiti della settimana\n"
            "🌟 **BestDeals** — Riepilogo quotidiano delle migliori offerte"
        )
    },
    "help_title": {
        "fr": "Aide GameRadar",
        "en": "GameRadar Help",
        "es": "Ayuda GameRadar",
        "de": "GameRadar Hilfe",
        "it": "Guida GameRadar"
    },
    "status_ok": {
        "fr": "✅ Le bot est en ligne et fonctionne correctement.",
        "en": "✅ The bot is online and running fine.",
        "es": "✅ El bot está en línea y funcionando correctamente.",
        "de": "✅ Der Bot ist online und funktioniert einwandfrei.",
        "it": "✅ Il bot è online e funziona correttamente."
    },
    "lang_changed": {
        "fr": "🌍 La langue a été changée en **Français**.",
        "en": "🌍 Language has been set to **English**.",
        "es": "🌍 El idioma ha sido cambiado a **Español**.",
        "de": "🌍 Die Sprache wurde auf **Deutsch** geändert.",
        "it": "🌍 La lingua è stata impostata su **Italiano**."
    },
    "lang_invalid": {
        "fr": "❌ Langue invalide. Options : `es`, `fr`, `en`, `de`, `it`.",
        "en": "❌ Invalid language. Options: `es`, `fr`, `en`, `de`, `it`.",
        "es": "❌ Idioma inválido. Opciones: `es`, `fr`, `en`, `de`, `it`.",
        "de": "❌ Ungültige Sprache. Optionen: `de`, `fr`, `en`, `es`, `it`.",
        "it": "❌ Lingua non valida. Opzioni: `it`, `fr`, `en`, `es`, `de`."
    },
    "lang_current": {
        "fr": "🌍 Langue actuelle : **{lang}**\nLangues disponibles : `it`, `fr`, `en`, `es`, `de`\nUtilisez `$lang fr` ou `$lang en` pour changer.",
        "en": "🌍 Current language: **{lang}**\nAvailable languages: `it`, `fr`, `en`, `es`, `de`\nUse `$lang fr` or `$lang en` to change.",
        "es": "🌍 Idioma actual: **{lang}**\nIdiomas disponibles: `it`, `fr`, `en`, `es`, `de`\nUsa `$lang es` para cambiar.",
        "de": "🌍 Aktuelle Sprache: **{lang}**\nVerfügbare Sprachen: `it`, `fr`, `en`, `es`, `de`\nNutze `$lang de` zum Ändern.",
        "it": "🌍 Lingua attuale: **{lang}**\nLingue disponibili: `it`, `fr`, `en`, `es`, `de`\nUsa `$lang it` per cambiare."
    },
    "channel_set": {
        "fr": "✅ Salon configuré : <#{channel_id}>",
        "en": "✅ Channel set: <#{channel_id}>",
        "es": "✅ Canal configurado: <#{channel_id}>",
        "de": "✅ Kanal gesetzt: <#{channel_id}>",
        "it": "✅ Canale impostato: <#{channel_id}>"
    },
    "filters_current": {
        "fr": "📊 Filtres actuels :\n```\n{filters}\n```",
        "en": "📊 Current filters:\n```\n{filters}\n```",
        "es": "📊 Filtros actuales:\n```\n{filters}\n```",
        "de": "📊 Aktuelle Filter:\n```\n{filters}\n```",
        "it": "📊 Filtri attuali:\n```\n{filters}\n```"
    },
    "filter_invalid_value": {
        "fr": "❌ Valeur invalide pour {key}: {value}",
        "en": "❌ Invalid value for {key}: {value}",
        "es": "❌ Valor inválido para {key}: {value}",
        "de": "❌ Ungültiger Wert für {key}: {value}",
        "it": "❌ Valore non valido per {key}: {value}"
    },
    "filter_unknown": {
        "fr": "❌ Filtre inconnu : {filter_key}",
        "en": "❌ Unknown filter: {filter_key}",
        "es": "❌ Filtro desconocido: {filter_key}",
        "de": "❌ Unbekannter Filter: {filter_key}",
        "it": "❌ Filtro sconosciuto: {filter_key}"
    },
    "filters_updated": {
        "fr": "✅ Filtres mis à jour.",
        "en": "✅ Filters updated.",
        "es": "✅ Filtros actualizados.",
        "de": "✅ Filter aktualisiert.",
        "it": "✅ Filtri aggiornati."
    },
    "bestdeals_header": {
        "fr": "🌟 Meilleures offres du jour",
        "en": "🌟 Today's Best Deals",
        "es": "🌟 Mejores ofertas de hoy",
        "de": "🌟 Beste Angebote des Tages",
        "it": "🌟 Migliori offerte di oggi"
    },
    "bestdeals_free": {
        "fr": "Jeux gratuits les plus récents",
        "en": "Most Recent Free Games",
        "es": "Juegos gratuitos más recientes",
        "de": "Neueste Gratis-Spiele",
        "it": "Giochi gratuiti più recenti"
    },
    "bestdeals_line": {
        "fr": "**{title}** — {discount}% — {price}€\n{url}",
        "en": "**{title}** — {discount}% off — {price}€\n{url}",
        "es": "**{title}** — {discount}% de descuento — {price}€\n{url}",
        "de": "**{title}** — {discount}% Rabatt — {price}€\n{url}",
        "it": "**{title}** — {discount}% di sconto — {price}€\n{url}"
    },
    "free_line": {
        "fr": "**{title}** — Expire le: {expiry}\n{url}",
        "en": "**{title}** — Expires: {expiry}\n{url}",
        "es": "**{title}** — Expira: {expiry}\n{url}",
        "de": "**{title}** — Endet am: {expiry}\n{url}",
        "it": "**{title}** — Scade il: {expiry}\n{url}"
    },
    "no_deals": {
        "fr": "❌ Aucune offre trouvée.",
        "en": "❌ No deals found.",
        "es": "❌ No se encontraron ofertas.",
        "de": "❌ Keine Angebote gefunden.",
        "it": "❌ Nessuna offerta trovata."
    },
    "no_free": {
        "fr": "❌ Aucun jeu gratuit trouvé.",
        "en": "❌ No free games found.",
        "es": "❌ No se encontraron juegos gratuitos.",
        "de": "❌ Keine Gratis-Spiele gefunden.",
        "it": "❌ Nessun gioco gratuito trovato."
    },
    "unknown_command": {
        "fr": "❌ Commande inconnue.",
        "en": "❌ Unknown command.",
        "es": "❌ Comando desconocido.",
        "de": "❌ Unbekannter Befehl.",
        "it": "❌ Comando sconosciuto."
    }
}

def tr(key, guild_id=None, **kwargs):
    configs = load_guild_config()
    lang = "en"
    if guild_id and str(guild_id) in configs:
        lang = configs[str(guild_id)].get("lang", "en")

    if key not in translations:
        return key
    return translations[key].get(lang, translations[key]["en"]).format(**kwargs)



# ====== util ======
def load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {"steam": {}, "cheapshark": {}, "epic_free": {}}

def save_seen(data):
    tmp = SEEN_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(SEEN_FILE)


def need_refresh_popular():
    global last_popular_refresh
    now = asyncio.get_event_loop().time()
    if now - last_popular_refresh > POPULAR_REFRESH_INTERVAL:
        last_popular_refresh = now
        return True
    return False

def load_guild_config():
    if GUILDS_FILE.exists():
        return json.loads(GUILDS_FILE.read_text())
    return {}

def save_guild_config(config):
    tmp = GUILDS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    tmp.replace(GUILDS_FILE)

def default_guild_config():
    return {
        "channel_id": None,
        "lang": "en",
        "filters": {
            "min_discount": MIN_DISCOUNT,
            "max_price": MAX_PRICE,
            "best_discount": BEST_DISCOUNT,
            "best_price": BEST_PRICE,
            "epic": True,
            "steam": True,
            "cheapshark": True,
            "bestdeals": False,
            "silent": False,
            "notifs": POLL_INTERVAL,
            "bestsnotifs": BEST_INTERVAL
        },
        "bests": [],
        "free": []
    }

def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"\b(digital|deluxe|ultimate|gold|definitive|goty|game of the year|edition|bundle|pack)\b", "", t)
    t = re.sub(r"[-:()]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    return t

# ====== fetchers ======
async def fetch_steam_app(session, appid):
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
    async with session.get(url, timeout=30) as r:
        return await r.json()

async def fetch_cheapshark_deals(session, page_size=20):
    url = f"https://www.cheapshark.com/api/1.0/deals?&pageSize={page_size}"
    async with session.get(url, timeout=30) as r:
        return await r.json()

async def fetch_epic_free_with_gamerpower(session):
    url = "https://www.gamerpower.com/api/giveaways?platform=epic-games-store"
    async with session.get(url, timeout=30) as r:
        if r.status == 200:
            return await r.json()
        else:
            text = await r.text()
            print(f"Erreur GamerPower: status={r.status}, body={text}")
            return None

async def fetch_steam_app_list(session):
    url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
    async with session.get(url, timeout=60) as r:
        if r.status == 200:
            j = await r.json()
            apps = j.get("applist", {}).get("apps", [])
            return apps
        else:
            print(f"Erreur fetch_steam_app_list: status {r.status}")
            return []

async def fetch_steam_most_played(session, top_n=50):
    url = "https://api.steampowered.com/ISteamChartsService/GetMostPlayedGames/v1/"
    async with session.get(url, timeout=30) as r:
        if r.status == 200:
            data = await r.json()
            ranks = data.get("response", {}).get("ranks", [])
            return ranks[:top_n]
        else:
            print(f"Erreur fetch_steam_most_played: status {r.status}")
            return []

def try_parse_date(s):
    if not s:
        return None
    try:
        s2 = s.strip().replace("Z", "+00:00") if s.strip().endswith("Z") else s.strip()
        return datetime.datetime.fromisoformat(s2)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


# ====== Bot ======
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)
seen = load_seen()
first_run = True

# === Events ===

@bot.event
async def on_ready():
    print("Bot ready:", bot.user)
    if not check_loop.is_running():
        check_loop.start()
    if not bestdeals_loop.is_running():
        bestdeals_loop.start()

@bot.event
async def on_guild_join(guild):
    configs = load_guild_config()
    if str(guild.id) not in configs:
        configs[str(guild.id)] = default_guild_config()
        save_guild_config(configs)
        print(f"New config created for the guild {guild.name} ({guild.id})")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(tr("unknown_command", guild_id=getattr(ctx.guild, "id", None)))
    else:
        raise error

# === Commands ===

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title=tr("help_title", guild_id=ctx.guild.id),
        description=tr("help_text", guild_id=ctx.guild.id),
        color=discord.Color.orange()
    )
    embed.add_field(
        name=" ",
        value=tr("help_loops", guild_id=ctx.guild.id),
        inline=False
    )
    embed.set_footer(text="GameRadar Bot")
    await ctx.send(embed=embed)

@bot.command(name="status")
async def status_command(ctx):
    await ctx.send(tr("status_ok"))

@bot.command(name="lang")
async def lang_command(ctx, lang: str = None):
    configs = load_guild_config()
    gid = str(ctx.guild.id)
    if gid not in configs:
        configs[gid] = default_guild_config()

    allowed_langs = {"es", "fr", "en", "de", "it"}

    if lang is None:
        await ctx.send(tr("lang_current", guild_id=ctx.guild.id, lang=configs[gid]["lang"].upper()))
    elif lang.lower() in allowed_langs:
        configs[gid]["lang"] = lang.lower()
        save_guild_config(configs)
        await ctx.send(tr("lang_changed", guild_id=ctx.guild.id))
    else:
        await ctx.send(tr("lang_invalid", guild_id=ctx.guild.id))

@bot.command(name="setchannel")
@commands.has_permissions(administrator=True)
async def setchannel_command(ctx):
    configs = load_guild_config()
    gid = str(ctx.guild.id)
    if gid not in configs:
        configs[gid] = default_guild_config()
    configs[gid]["channel_id"] = ctx.channel.id
    save_guild_config(configs)
    await ctx.send(tr("channel_set", guild_id=ctx.guild.id, channel_id=ctx.channel.id))

@bot.command(name="filters")
@commands.has_permissions(administrator=True)
async def filters_command(ctx, *, args=None):
    configs = load_guild_config()
    gid = str(ctx.guild.id)
    if gid not in configs:
        configs[gid] = default_guild_config()

    filters = configs[gid]["filters"]

    allowed_keys = {
        "epic", "steam", "cheapshark", "bestdeals", "silent",
        "min_discount", "max_price", "best_discount", "best_price",
        "notifs", "bestsnotifs"
    }

    if not args:
        txt = "\n".join([f"{k} = {v}" for k, v in filters.items()])
        await ctx.send(tr("filters_current", guild_id=ctx.guild.id, filters=txt))
        return

    for arg in args.split():
        if "=" not in arg:
            await ctx.send(tr("filter_unknown", guild_id=ctx.guild.id, filter_key=arg.strip()))
            return
        key, _ = arg.split("=", 1)
        key = key.strip().lower()
        if key not in allowed_keys:
            await ctx.send(tr("filter_unknown", guild_id=ctx.guild.id, filter_key=key))
            return

    for arg in args.split():
        if "=" not in arg:
            continue
        key, value = arg.split("=", 1)
        key = key.strip().lower()
        value = value.strip().lower()

        if key in ["epic", "steam", "cheapshark", "bestdeals", "silent"]:
            filters[key] = value in {"1", "true", "on", "yes"}
        elif key in ["min_discount", "best_discount"]:
            try:
                val = int(value)
                if not (0 <= val <= 100):
                    raise ValueError
                filters[key] = val
            except Exception:
                await ctx.send(tr("filter_invalid_value", guild_id=ctx.guild.id, key=key, value=value))
                return
        elif key in ["max_price", "best_price"]:
            try:
                val = float(value)
                if not (0 <= val <= 1000):
                    raise ValueError
                filters[key] = val
            except Exception:
                await ctx.send(tr("filter_invalid_value", guild_id=ctx.guild.id, key=key, value=value))
                return
        elif key == "notifs":
            try:
                val = int(value)
                if not (1 <= val <= 8):
                    raise ValueError
                filters[key] = val
            except Exception:
                await ctx.send(tr("filter_invalid_value", guild_id=ctx.guild.id, key=key, value=value))
                return
        elif key == "bestsnotifs":
            try:
                val = int(value)
                if not (1 <= val <= 8):
                    raise ValueError
                filters[key] = val
            except Exception:
                await ctx.send(tr("filter_invalid_value", guild_id=ctx.guild.id, key=key, value=value))
                return

    configs[gid]["filters"] = filters
    save_guild_config(configs)
    await ctx.send(tr("filters_updated", guild_id=ctx.guild.id))


@bot.command(name="bests")
async def bests_command(ctx):
    configs = load_guild_config()
    gid = str(ctx.guild.id)
    if gid not in configs:
        await ctx.send(tr("no_deals", guild_id=ctx.guild.id))
        return

    bests = configs[gid].get("bests", [])

    if not bests:
        await ctx.send(tr("no_deals", guild_id=ctx.guild.id))
        return

    embed = discord.Embed(
        title=tr("bestdeals_header", guild_id=ctx.guild.id),
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now(datetime.UTC)
    )

    desc_lines = []
    for deal in bests:
        line = tr("bestdeals_line", guild_id=ctx.guild.id,
                  title=deal['title'],
                  discount=deal['discount'],
                  price=deal['price'],
                  url=deal['url'])
        desc_lines.append(line)
    embed.add_field(name="🔥 Top 5", value="\n\n".join(desc_lines), inline=False)

    await ctx.send(embed=embed)


@bot.command(name="free")
async def free_command(ctx):
    configs = load_guild_config()
    gid = str(ctx.guild.id)
    if gid not in configs:
        await ctx.send(tr("no_free", guild_id=ctx.guild.id))
        return

    frees = configs[gid].get("free", [])

    if not frees:
        await ctx.send(tr("no_free", guild_id=ctx.guild.id))
        return

    embed = discord.Embed(
        title=tr("bestdeals_free", guild_id=ctx.guild.id),
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.UTC)
    )

    desc_lines = []
    for game in frees:
        expiry = game.get("expiry") or "N/A"
        line = tr("free_line", guild_id=ctx.guild.id,
                  title=game['title'],
                  expiry=expiry,
                  url=game['url'])
        desc_lines.append(line)
    embed.add_field(name="🎁 Free Games", value="\n\n".join(desc_lines), inline=False)

    await ctx.send(embed=embed)



# === Loop ===

# Helper to fetch steam app details with concurrency limit
async def _fetch_steam_details_concurrent(session, appids, concurrency=10):
    sem = asyncio.Semaphore(concurrency)

    async def _safe_fetch(aid):
        async with sem:
            try:
                return await fetch_steam_app(session, aid)
            except Exception as e:
                print(f"Error fetching steam app {aid}: {e}")
                return None

    tasks = [_safe_fetch(a) for a in appids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

#Main loop
@tasks.loop(hours=6)
async def check_loop():
    """
    - Fetch once Steam (popular appids), CheapShark, Epic (gamerpower)
    - Build normalized lists:
        steam_promos: [{'title','discount','price','url','appid'}...]
        cheap_promos: [{'title','discount','price','url','dealID'}...]
        epic_promos: [{'title','expiry','url','id'}...]
    - For each guild:
      * use existing filters to:
         - send immediate notifications (like before),
         - create and save 'bests' (max 5) and 'free' (max 3) in guilds.json
    """
    global seen, steam_popular_appids, first_run, loopcycle

    if 'loopcycle' not in globals():
        loopcycle = 1
    else:
        loopcycle += 1
        if loopcycle > 48 / POLL_INTERVAL:
            loopcycle = 1
    
    configs = load_guild_config()
    if not configs:
        return

    async with aiohttp.ClientSession() as session:

        # Fetch Steam popular appids once (if needed)
        if not steam_popular_appids or need_refresh_popular():
            popular = await fetch_steam_most_played(session, top_n=100)
            steam_popular_appids = [g["appid"] for g in popular if "appid" in g]
            print(f"Refresh popular Steam Games list, {len(steam_popular_appids)} appids.")

        steam_promos = []
        try:
            steam_results = await _fetch_steam_details_concurrent(session, steam_popular_appids, concurrency=12)
            for res in steam_results:
                if not res or not isinstance(res, dict):
                    continue
                for key, info in res.items():
                    try:
                        if not isinstance(info, dict) or not info.get("success"):
                            continue
                        d = info.get("data", {})
                        if d.get("type") != "game":
                            continue
                        price_overview = d.get("price_overview")
                        name = d.get("name", f"App {key}")
                        if price_overview:
                            final = price_overview.get("final")
                            discount = price_overview.get("discount_percent", 0)
                            if final is None:
                                continue
                            final_euro = final / 100.0
                            appid_int = int(key)
                            steam_promos.append({
                                "source": "steam",
                                "title": name,
                                "discount": int(discount),
                                "price": float(final_euro),
                                "url": f"https://store.steampowered.com/app/{appid_int}",
                                "appid": appid_int,
                            })
                    except Exception as e:
                        print("Error parsing steam response:", e)
        except Exception as e:
            print("Erreur lors du fetch Steam details:", e)

        # Fetch CheapShark once
        cheap_promos = []
        try:
            deals = await fetch_cheapshark_deals(session, page_size=60)
            if isinstance(deals, list):
                for deal in deals:
                    try:
                        dealID = deal.get("dealID")
                        title = deal.get("title", "Unknown")
                        savings = float(deal.get("savings", "0") or 0)
                        price = None
                        for key in ["salePrice", "price", "normalPrice"]:
                            val = deal.get(key)
                            if val not in (None, "", "0", "0.0"):
                                try:
                                    price = float(val)
                                    break
                                except:
                                    pass
                        if price is None or price == 0.0:
                            continue
                        cheap_promos.append({
                            "source": "cheapshark",
                            "title": title,
                            "discount": int(savings),
                            "price": float(price),
                            "url": f"https://www.cheapshark.com/redirect?dealID={dealID}",
                            "dealID": dealID,
                            "internalName": deal.get("internalName")
                        })
                    except Exception as e2:
                        print("Error parsing cheapshark deal:", e2)
        except Exception as e:
            print("Erreur CheapShark:", e)

        # Fetch Epic freebies once
        epic_promos = []
        try:
            epic_gp = await fetch_epic_free_with_gamerpower(session)
            if epic_gp:
                for giving in epic_gp:
                    try:
                        title = giving.get("title") or giving.get("name")
                        expiry = giving.get("end_date") or giving.get("ends") or giving.get("end")
                        giveaway_id = giving.get("id")
                        url_gp = giving.get("open_giveaway_url") or giving.get("url")
                        unique_key = f"{title}:{expiry}:{giveaway_id}"
                        epic_promos.append({
                            "source": "epic",
                            "title": title,
                            "expiry": expiry,
                            "expiry_dt": try_parse_date(expiry),
                            "url": url_gp,
                            "id": giveaway_id,
                            "unique_key": unique_key
                        })
                    except Exception as e:
                        print("Error parsing epic giveaway:", e)
        except Exception as e:
            print("Erreur Epic API:", e)

        # Now for each guild: notify and compute bests/free and store them
        # We will reuse steam_promos, cheap_promos, epic_promos
        configs_modified = False

        for gid, cfg in configs.items():
            guild_id = int(gid)
            channel_id = cfg.get("channel_id")
            if not channel_id:
                continue

            channel = bot.get_channel(channel_id)
            if channel is None:
                continue

            filters = cfg.get("filters", default_guild_config()["filters"])

            # Notifications (Steam)
            if (filters.get("steam", True) and not filters.get("silent", False) and (loopcycle % int(filters.get("notifs", POLL_INTERVAL)) == 0)):
                current_promos_steam_keys = {}
                for sp in steam_promos:
                    try:
                        name = sp["title"]
                        name_key = name.strip().lower()
                        current_promos_steam_keys[name_key] = sp["price"]
                        previous_price = seen["steam"].get(name_key)

                        if sp["discount"] >= filters["min_discount"] and sp["price"] <= filters["max_price"]:
                            if previous_price is None or int(float(previous_price)) > int(sp["price"] * 100):
                                seen["steam"][name_key] = str(int(sp["price"] * 100))
                                save_seen(seen)
                                if not first_run:
                                    msg = tr("steam_deal", guild_id=guild_id,
                                             title=name,
                                             discount=sp["discount"],
                                             price=sp["price"],
                                             url=sp["url"])
                                    try:
                                        await channel.send(msg)
                                    except Exception as e:
                                        print(f"[{gid}] Error sending steam message:", e)
                    except Exception as e:
                        print(f"[{gid}] Error processing steam promo:", e)

                to_remove = [k for k in seen["steam"] if k not in current_promos_steam_keys]
                for k in to_remove:
                    del seen["steam"][k]
                if to_remove:
                    save_seen(seen)

            # Notifications (CheapShark)
            if filters.get("cheapshark", True) and not filters.get("silent", False) and (loopcycle % int(filters.get("notifs", POLL_INTERVAL)) == 0):
                current_promos_cs = {}
                for cp in cheap_promos:
                    try:
                        dealID = cp.get("dealID")
                        title = cp.get("title")
                        savings = cp.get("discount", 0)
                        price = cp.get("price")
                        current_promos_cs[dealID] = cp.get("internalName")
                        seen_key = dealID
                        if savings >= filters["min_discount"] and price <= filters["max_price"]:
                            if seen["cheapshark"].get(seen_key) != cp.get("internalName"):
                                seen["cheapshark"][seen_key] = cp.get("internalName")
                                save_seen(seen)
                                if not first_run:
                                    msg = tr("cheapshark_deal", guild_id=guild_id,
                                             title=title,
                                             savings=int(savings),
                                             price=price,
                                             url=cp.get("url"))
                                    try:
                                        await channel.send(msg)
                                    except Exception as e:
                                        print(f"[{gid}] Error sending cheapshark message:", e)
                    except Exception as e:
                        print(f"[{gid}] Error processing cheapshark promo:", e)

                to_remove = [d for d in seen["cheapshark"] if d not in current_promos_cs]
                for d in to_remove:
                    del seen["cheapshark"][d]
                if to_remove:
                    save_seen(seen)

            # Notifications (Epic freebies)
            if filters.get("epic", True) and not filters.get("silent", False) and (loopcycle % int(filters.get("notifs", POLL_INTERVAL)) == 0):
                current_promos_epic = {}
                for eg in epic_promos:
                    try:
                        title = eg.get("title")
                        expiry = eg.get("expiry")
                        giveaway_id = eg.get("id")
                        unique_key = eg.get("unique_key")
                        current_promos_epic[unique_key] = unique_key
                        if seen["epic_free"].get(unique_key) != unique_key:
                            seen["epic_free"][unique_key] = unique_key
                            save_seen(seen)
                            if not first_run:
                                msg = tr("epic_free", guild_id=guild_id,
                                         title=title,
                                         expiry=expiry,
                                         url=eg.get("url"))
                                try:
                                    await channel.send(msg)
                                except Exception as e:
                                    print(f"[{gid}] Error sending epic message:", e)
                    except Exception as e:
                        print(f"[{gid}] Error processing epic promo:", e)

                to_remove = [k for k in seen["epic_free"] if k not in current_promos_epic]
                for k in to_remove:
                    del seen["epic_free"][k]
                if to_remove:
                    save_seen(seen)

            # Compute bests + free for this guild and store in config
            combined = []
            if filters.get("steam", True):
                combined.extend(steam_promos)
            if filters.get("cheapshark", True):
                combined.extend(cheap_promos)

            best_discount_min = filters.get("best_discount", BEST_DISCOUNT)
            best_price_max = filters.get("best_price", BEST_PRICE)

            filtered = [p for p in combined if p.get("discount", 0) >= best_discount_min and p.get("price", float("inf")) <= best_price_max]

            filtered.sort(
                key=lambda x: (
                    -int(x.get("source") == "steam" and x.get("appid") in steam_popular_appids),
                    -int(x.get("discount", 0)),
                    float(x.get("price", float("inf")))
                )
            )

            bests_for_guild = []
            seen_titles = set()

            for p in filtered:
                title_key = normalize_title(p.get("title", ""))

                if title_key in seen_titles:
                    continue
                seen_titles.add(title_key)

                bests_for_guild.append({
                    "title": p.get("title"),
                    "discount": int(p.get("discount", 0)),
                    "price": float(p.get("price", 0.0)),
                    "url": p.get("url"),
                    "source": p.get("source"),
                    "id": p.get("appid") or p.get("dealID") or p.get("id"),
                    "popularity": 1 if (p.get("source") == "steam" and p.get("appid") in steam_popular_appids) else 0
                })

                if len(bests_for_guild) >= 5:
                    break

            frees_candidates = epic_promos.copy()
            frees_candidates.sort(key=lambda x: (x.get("expiry_dt") is None, x.get("expiry_dt") or datetime.datetime.max))
            frees_for_guild = []
            for eg in frees_candidates[:3]:
                frees_for_guild.append({
                    "title": eg.get("title"),
                    "expiry": eg.get("expiry"),
                    "url": eg.get("url"),
                    "id": eg.get("id")
                })

            if cfg.get("bests") != bests_for_guild or cfg.get("free") != frees_for_guild:
                cfg["bests"] = bests_for_guild
                cfg["free"] = frees_for_guild
                configs_modified = True

        if configs_modified:
            save_guild_config(configs)

        if first_run:
            first_run = False


# Daily bestdeals loop
@tasks.loop(hours=24)
async def bestdeals_loop():
    configs = load_guild_config()
    if not configs:
        return

    for gid, cfg in configs.items():
        guild_id = int(gid)
        channel_id = cfg.get("channel_id")
        if not channel_id:
            continue

        filters = cfg.get("filters", {})
        if not filters.get("bestdeals", False):
            continue

        channel = bot.get_channel(channel_id)
        if channel is None:
            continue

        bests = cfg.get("bests", []) or []
        frees = cfg.get("free", []) or []

        if not bests and not frees:
            continue

        embed = discord.Embed(
            title=tr("bestdeals_header", guild_id=guild_id),
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.UTC)
        )

        if bests:
            desc_lines = []
            for deal in bests:
                line = tr("bestdeals_line", guild_id=guild_id,
                        title=deal['title'],
                        discount=deal['discount'],
                        price=deal['price'],
                        url=deal['url'])
                desc_lines.append(line)
            embed.add_field(name="🔥 Top 5", value="\n\n".join(desc_lines), inline=False)

        if frees:
            desc_lines = []
            for game in frees:
                expiry = game.get("expiry") or "N/A"
                line = tr("free_line", guild_id=guild_id,
                        title=game['title'],
                        expiry=expiry,
                        url=game['url'])
                desc_lines.append(line)
            embed.add_field(name=tr("bestdeals_free", guild_id=guild_id), value="\n\n".join(desc_lines), inline=False)

        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"[{gid}] Error sending bestdeals embed:", e)


# start
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
