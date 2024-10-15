import discord, asyncio
import os, logging

# Setup bot intents and client
intents = discord.Intents.default()
intents.guilds = True
intents.guild_messages = True  # Allows caching of channels and messages
intents.messages = True  # Enables message event handling
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    logging.info(f'Bot connected as {bot.user.name}')
    for guild in bot.guilds:
        print(f'Connected to guild: {guild.name} (ID: {guild.id})')
        
    # Get the channel from the bot's internal cache using the channel ID
    channel = bot.get_channel(976277324393762856)
    
    if channel is None:
        logging.error("Channel not found. Double-check the ID.")
        return

    # Send an embed to the found channel
    #embed = discord.Embed(title="Test Embed", description="This is a test.")
    #try:
        #await channel.send(embed=embed)
        #logging.info(f"Embed sent to channel: {channel.name} (ID: {channel.id})")
    #except discord.Forbidden:
        #logging.error(f"Bot doesn't have permission to send messages to {channel.name}")
    #except Exception as e:
        #logging.error(f"Failed to send embed: {e}")

bot_started = False

def run_bot():
    global bot_started
    if bot_started:
        logging.info("Bot is already running, skipping...")
        return
    
    logging.info("Starting Discord bot...")
    bot_started = True  # Mark the bot as started
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    if DISCORD_BOT_TOKEN:
        bot.run(DISCORD_BOT_TOKEN)
    else:
        logging.error("No Discord bot token provided.")
        
        
def trigger_embed_sending(discord_channel_id, embed):
    logging.info(f'Triggering embed sending for channel ID: {discord_channel_id}')
    
    # Schedule the send_embed coroutine in the bot's event loop
    bot.loop.create_task(send_embed(discord_channel_id, embed))

async def send_embed(discord_channel_id, embed, video_url=None):
    logging.info(f'Attempting to send an embed to channel ID: {discord_channel_id}')
    
    try:
        # Fetch the channel from Discord API
        channel = await bot.fetch_channel(discord_channel_id)
        logging.info(f'Channel fetched: {channel.name} (ID: {channel.id}). Sending embed...')
        await channel.send(embed=embed)
        logging.info('Embed sent successfully.')
        #if video_url:
            #await channel.send(video_url)  # Send the video URL separately

    except discord.Forbidden:
        logging.error(f'Bot doesn\'t have permission to send messages to {channel.name}')
    except discord.HTTPException as e:
        logging.error(f'Failed to send embed due to an HTTP error: {e}')
    except Exception as e:
        logging.error(f'An unexpected error occurred: {e}')


