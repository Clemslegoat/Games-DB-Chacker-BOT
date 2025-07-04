
import discord
from discord.ext import commands, tasks
import requests
import json
import asyncio
from datetime import datetime, time
import pytz
import os
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

# Configuration sécurisée
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
JSONBIN_URL = os.getenv("JSONBIN_URL")
JSONBIN_API_KEY = os.getenv("JSONBIN_API_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)
known_games = set()

class GameNotifier:
    def __init__(self):
        self.session = requests.Session()
        if JSONBIN_API_KEY:
            self.session.headers.update({
                'X-Access-Key': JSONBIN_API_KEY
            })
    
    async def fetch_database(self):
        try:
            response = self.session.get(JSONBIN_URL)
            response.raise_for_status()
            return response.json().get('record', {})
        except requests.RequestException as e:
            print(f"Erreur lors de la récupération de la DB: {e}")
            return {}
    
    async def create_game_embed(self, game_key, game_data):
        embed = discord.Embed(
            title="🎮 Nouveau jeu ajouté !",
            color=0x00ff00,
            timestamp=datetime.now(FRENCH_TZ)
        )
        if 'description' in game_data and game_data['description']:
            description = game_data['description'][:1000]
            if len(game_data['description']) > 1000:
                description += "..."
            embed.description = f"**{game_data['official_name']}**{description}"
        else:
            embed.description = f"**{game_data['official_name']}**"
        if 'image_url' in game_data and game_data['image_url']:
            embed.set_image(url=game_data['image_url'])
        embed.set_footer(text=f"id: {game_key}")
        return embed
    
    async def check_for_new_games(self):
        global known_games
        database = await self.fetch_database()
        if not database:
            return
        new_games = []
        current_games = set(database.keys())
        if not known_games:
            known_games = current_games
            print(f"Base initialisée avec {len(known_games)} jeux")
            return
        new_game_keys = current_games - known_games
        for game_key in new_game_keys:
            game_data = database[game_key]
            new_games.append((game_key, game_data))
        known_games = current_games
        return new_games

notifier = GameNotifier()

@bot.event
async def on_ready():
    print(f'Surveillance de la base de données activée')
    check_database.start()

FRENCH_TZ = pytz.timezone('Europe/Paris')

@tasks.loop(time=time(hour=10, minute=0))
async def check_database():
    try:
        new_games = await notifier.check_for_new_games()
        if new_games:
            channel = bot.get_channel(CHANNEL_ID)
            if not channel:
                print(f"Canal {CHANNEL_ID} introuvable!")
                return
            for game_key, game_data in new_games:
                embed = await notifier.create_game_embed(game_key, game_data)
                await channel.send(embed=embed)
                print(f"Nouveau jeu notifié: {game_data.get('official_name', game_key)}")
                await asyncio.sleep(1)
    except Exception as e:
        print(f"Erreur dans check_database: {e}")

@check_database.before_loop
async def before_check_database():
    await bot.wait_until_ready()

@bot.command(name='status')
async def status(ctx):
    embed = discord.Embed(
        title="📊 Statut du Bot",
        color=0x0099ff,
        timestamp=datetime.now()
    )
    embed.add_field(
        name="Jeux surveillés | Statut surveillance",
        value=f"{len(known_games)} | {'🟢 Actif' if check_database.is_running() else '🔴 Inactif'}",
        inline=False
    )
    embed.add_field(name="Prochaine vérification", value="Tous les jours à 10h00 (heure française)", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='check_now')
@commands.has_permissions(administrator=True)
async def manual_check(ctx):
    await ctx.send("🔍 Vérification manuelle en cours...")
    try:
        new_games = await notifier.check_for_new_games()
        if new_games:
            for game_key, game_data in new_games:
                embed = await notifier.create_game_embed(game_key, game_data)
                await ctx.send(embed=embed)
        else:
            await ctx.send("ℹ️ Aucun nouveau jeu détecté.")
    except Exception as e:
        await ctx.send(f"❌ Erreur lors de la vérification: {str(e)}")

@bot.command(name='reset_db')
@commands.has_permissions(administrator=True)
async def reset_database(ctx):
    global known_games
    known_games.clear()
    await ctx.send("🔄 Base de données locale réinitialisée. La prochaine vérification va re-scanner tous les jeux.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Vous n'avez pas les permissions nécessaires pour cette commande.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"Erreur de commande: {error}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
