import discord
import aiohttp
import asyncio
from . import config

FLASK_API_URL = "http://127.0.0.1:5000/api"

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Discord bot has logged in as {client.user}')

@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Respond to a simple test command
    if message.content.startswith('$hello'):
        await message.channel.send('Hello!')
        return

    # Check if the message is a prompt for our Flask API
    if message.content.startswith('$prompt'):
        prompt_text = message.content.replace('$prompt', '').strip()
        
        if not prompt_text:
            await message.channel.send("Please provide a prompt after the command. Example: `$prompt What is the future of gaming?`")
            return

        # Fetch message history to provide conversational context
        history_messages = []
        async for msg in message.channel.history(limit=10):
            # We add them in reverse to maintain chronological order
            history_messages.insert(0, f"{msg.author.name}: {msg.content}")
        
        chat_history = "\n".join(history_messages)
            
        try:
            async with aiohttp.ClientSession() as session:
            payload = {
                "prompt": prompt_text,
                "history": chat_history
            }
                async with session.post(f"{FLASK_API_URL}/prompt", json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
            api_response = data.get("response", "Sorry, I couldn't get a valid response from the API.")
            print(f"Received response from Flask API: '{api_response}'")

            # Split the response into chunks of 2000 characters to stay within Discord's limit
            if len(api_response) > 2000:
                for i in range(0, len(api_response), 2000):
                    chunk = api_response[i:i+2000]
                    await message.channel.send(chunk)
            else:
                await message.channel.send(api_response)
                    else:
                        print(f"Error from Flask API: {response.status}")
                        await message.channel.send("Sorry, I received an error from my own API.")
            
        except aiohttp.ClientError as e:
            print(f"Error calling Flask API: {e}")
            await message.channel.send("Sorry, I had trouble connecting to my own API. Please check if the Flask server is running.")

    # Check if the user is uploading a log file
    if message.content.lower().startswith('$log'):
        if not message.attachments:
            await message.channel.send("Please attach a Markdown (.md) file with the `$log` command.")
            return

        attachment = message.attachments[0]
        if not attachment.filename.endswith('.md'):
            await message.channel.send("Invalid file type. Please upload a `.md` file.")
            return
            
        try:
            file_content_bytes = await attachment.read()
            file_content = file_content_bytes.decode('utf-8')

            # Call the new Flask API endpoint for logging
            log_api_url = f"{FLASK_API_URL}/submit_log"
            payload = {
                "filename": attachment.filename,
                "content": file_content
            }
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(log_api_url, json=payload) as response:
                        data = await response.json()
                        if response.status == 200:
            await message.channel.send(data.get("message", "Log processed."))
                        else:
                            await message.channel.send(data.get("error", "Failed to process log."))
            except aiohttp.ClientError as e:
                print(f"Error processing log file: {e}")
                await message.channel.send("Sorry, there was an error processing your log file.")

        except Exception as e:
            print(f"Error processing log file: {e}")
            await message.channel.send("Sorry, there was an error processing your log file.")

    # Check if the user wants to see a specific log
    if message.content.lower().startswith('$showlog'):
        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("Please provide a date. Example: `$showlog 2025-06-12`")
            return
        
        log_date_str = parts[1]
        get_log_api_url = f"{FLASK_API_URL}/get_log/{log_date_str}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(get_log_api_url) as response:
                    if response.status == 200:
                        data = await response.json()
            log_content = data.get("content", "No content found.")
            
            # Format the response to be more readable
            formatted_response = (
                f"**Log for {data.get('log_date')}** (Last Updated: {data.get('last_updated')})\n"
                f"------------------------------------\n"
                f"{log_content}"
            )

            # Chunk the response if it's too long
            if len(formatted_response) > 2000:
                for i in range(0, len(formatted_response), 1900): # Use 1900 to be safe
                    chunk = formatted_response[i:i+1900]
                    await message.channel.send(chunk)
            else:
                await message.channel.send(formatted_response)
                    elif response.status == 404:
                await message.channel.send(f"I don't have a log for the date `{log_date_str}`.")
            else:
                        data = await response.json()
                        await message.channel.send(f"An error occurred while fetching the log: {data.get('error')}")
        except aiohttp.ClientError as e:
            print(f"Error showing log file: {e}")
            await message.channel.send("Sorry, there was an error retrieving that log.")

    # New command for managing Riot Summoner info
    if message.content.lower().startswith('$summ'):
        parts = message.content.split()
        command = parts[1].lower() if len(parts) > 1 else None

        if command == 'set':
            if len(parts) < 3:
                await message.channel.send("Please provide your Riot ID. Example: `$summ set YourName#TAG`")
                return
            
            riot_id_full = parts[2]
            if '#' not in riot_id_full:
                await message.channel.send("Invalid format. Please use `YourName#TAG`.")
                return

            summoner_name, summoner_tag = riot_id_full.split('#', 1)
            
            set_api_url = f"{FLASK_API_URL}/summ/set"
            payload = {
                "discord_id": message.author.id,
                "discord_name": message.author.name,
                "summoner_name": summoner_name,
                "summoner_tag": summoner_tag
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(set_api_url, json=payload) as response:
                        data = await response.json()
                        if response.status == 200:
                            await message.channel.send(f"Success! {data.get('message')}")
                        else:
                            await message.channel.send(f"Error: {data.get('error', 'An unknown error occurred.')}")

            except aiohttp.ClientError as e:
                print(f"Error calling /api/summ/set: {e}")
                await message.channel.send("Sorry, I had trouble connecting to my API to set your summoner name.")

        elif command == 'show':
            show_api_url = f"{FLASK_API_URL}/summ/show/{message.author.id}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(show_api_url) as response:
                        data = await response.json()
                        if response.status == 200:
                            # For testing, we'll show the PUUID as requested
                            response_msg = (
                                f"Linked Riot Account for {data.get('discord_name')}:\n"
                                f"**Summoner:** {data.get('summoner_name')}#{data.get('summoner_tag')}\n"
                                f"**PUUID:** `{data.get('puuid')}`"
                            )
                            await message.channel.send(response_msg)
                        else:
                            await message.channel.send(f"{data.get('error', 'An unknown error occurred.')}")

            except aiohttp.ClientError as e:
                print(f"Error calling /api/summ/show: {e}")
                await message.channel.send("Sorry, I had trouble connecting to my API to show your summoner name.")
        
        elif command == 'last':
            await message.channel.send("Analyzing your last game... This might take a moment.")
            last_game_api_url = f"{FLASK_API_URL}/summ/last/{message.author.id}"
            try:
                # Set a longer timeout for this request as it can take a while
                timeout = aiohttp.ClientTimeout(total=120)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(last_game_api_url) as response:
                        if response.status == 200:
                            data = await response.json()
                            roast = data.get("roast", "I'm speechless. No roast for you.")
                            # Split the response into chunks of 2000 characters to stay within Discord's limit
                            if len(roast) > 2000:
                                for i in range(0, len(roast), 2000):
                                    chunk = roast[i:i+2000]
                                    await message.channel.send(chunk)
                            else:
                                await message.channel.send(roast)
                        else:
                            data = await response.json()
                            await message.channel.send(f"Error: {data.get('error', 'An unknown error occurred.')}")

            except asyncio.TimeoutError:
                print(f"Timeout calling /api/summ/last")
                await message.channel.send("Sorry, the analysis took too long to complete. Please try again later.")
            except aiohttp.ClientError as e:
                print(f"Error calling /api/summ/last: {e}")
                await message.channel.send("Sorry, I had trouble connecting to my API to analyze your last game.")

        else:
            await message.channel.send("Invalid command. Use `$summ set <RiotID#TAG>`, `$summ show`, or `$summ last`.")

def run_bot():
    """Starts the discord bot."""
    if not config.DISCORD_BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN is not set. Please add it to your .env file.")
        return
    
    print("Starting Discord bot...")
    client.run(config.DISCORD_BOT_TOKEN) 