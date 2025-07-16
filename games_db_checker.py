import discord
from discord.ext import commands, tasks
import requests
import json
import asyncio
from datetime import datetime, time
import pytz
import os
from dotenv import load_dotenv
from discord import TextChannel

# Chargement des variables d'environnement
# load_dotenv() # Supprimé car Railway gère les variables d'environnement

# Configuration sécurisée
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
JSONBIN_URL = os.getenv("JSONBIN_URL")
JSONBIN_API_KEY = os.getenv("JSONBIN_API_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

# Vérification explicite
if not DISCORD_TOKEN:
    print("ERREUR: DISCORD_TOKEN manquant dans les variables Railway !")
if not JSONBIN_URL:
    print("ERREUR: JSONBIN_URL manquant dans les variables Railway !")
if not JSONBIN_API_KEY:
    print("ERREUR: JSONBIN_API_KEY manquant dans les variables Railway !")
if not CHANNEL_ID:
    print("ERREUR: CHANNEL_ID manquant ou incorrect dans les variables Railway !")

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
            embed.description = f"**{game_data['official_name']}**\n{description}"
        else:
            embed.description = f"**{game_data['official_name']}**"
        if 'image_url' in game_data and game_data['image_url']:
            embed.set_image(url=game_data['image_url'])
        embed.set_footer(text=f"id: {game_key}")
        return embed
    
    async def check_for_new_games(self):
        global known_games
        database = await self.fetch_database()
        print(f"[DEBUG] Contenu de la base récupérée : {list(database.keys())}")
        print(f"[DEBUG] known_games AVANT comparaison : {list(known_games)}")
        if not database:
            print("[DEBUG] Base vide ou inaccessible !")
            return []
        current_games = set(database.keys())
        new_game_keys = current_games - known_games
        print(f"[DEBUG] Nouveaux jeux détectés : {list(new_game_keys)}")
        new_games = [(game_key, database[game_key]) for game_key in new_game_keys]
        known_games = current_games
        print(f"[DEBUG] known_games APRÈS mise à jour : {list(known_games)}")
        return new_games

notifier = GameNotifier()

@bot.event
async def on_ready():
    print(f'Surveillance de la base de données activée')
    if not check_database.is_running():
        check_database.start()

FRENCH_TZ = pytz.timezone('Europe/Paris')

@tasks.loop(time=time(hour=10, minute=0, tzinfo=FRENCH_TZ))
async def check_database():
    print(f"[{datetime.now()}] [DEBUG] check_database lancé automatiquement (tâche planifiée)")
    try:
        print("[DEBUG] Appel de notifier.check_for_new_games() (tâche planifiée)")
        new_games = await notifier.check_for_new_games()
        print(f"[DEBUG] Résultat de check_for_new_games (tâche planifiée) : {new_games}")
        if new_games:
            print("[DEBUG] De nouveaux jeux ont été détectés (tâche planifiée)")
            channel = bot.get_channel(CHANNEL_ID)
            if not isinstance(channel, TextChannel):
                print(f"[ERREUR] Canal {CHANNEL_ID} n'est pas un TextChannel !")
                return
            print(f"[DEBUG] Récupération du channel avec ID {CHANNEL_ID} : {channel}")
            if not channel or not hasattr(channel, "send"):
                print(f"[ERREUR] Canal {CHANNEL_ID} introuvable ou de type incorrect !")
                return
            for game_key, game_data in new_games:
                print(f"[DEBUG] Envoi de la notification pour le jeu : {game_key}")
                embed = await notifier.create_game_embed(game_key, game_data)
                await channel.send(embed=embed)
                print(f"[INFO] Nouveau jeu notifié: {game_data.get('official_name', game_key)}")
                await asyncio.sleep(1)
            print("[DEBUG] Tous les nouveaux jeux ont été notifiés (tâche planifiée).")
        else:
            print("[DEBUG] Aucun nouveau jeu détecté lors de la vérification automatique (tâche planifiée).")
    except Exception as e:
        print(f"[ERREUR] Exception dans check_database (tâche planifiée): {e}")

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
