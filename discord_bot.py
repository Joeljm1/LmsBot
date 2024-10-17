import discord
from discord.ext import commands, tasks
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from database import Database
import sqlite3

# Load environment variables
load_dotenv()

# Constants
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
PORTAL_URL = 'https://lmsug23.iiitkottayam.ac.in'
LOGIN_URL = f'{PORTAL_URL}/login/index.php'
CALENDAR_URL = f'{PORTAL_URL}/calendar/view.php?view=upcoming'

# Set up Discord bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize database
db = Database('users.db')

class PortalMonitor:
    def __init__(self):
        self.session = None

    async def get_session(self):
        """Create or return an existing aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def login(self, username, password):
        """Attempt to log in to the LMS portal"""
        session = await self.get_session()
        try:
            # Clear cookies before attempting to log in
            session.cookie_jar.clear()
            
            # Get login token
            async with session.get(LOGIN_URL) as response:
                if response.status != 200:
                    print(f"Failed to access login page. Status code: {response.status}")
                    return False
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                login_token_element = soup.find('input', {'name': 'logintoken'})
                if login_token_element is None:
                    print("Login token not found on the page.")
                    return False
                login_token = login_token_element['value']

            # Attempt login
            login_data = {
                'username': username,
                'password': password,
                'logintoken': login_token
            }
            async with session.post(LOGIN_URL, data=login_data, allow_redirects=False) as response:
                if response.status != 303:  # Expecting a redirect after successful login
                    print(f"Login failed. Status code: {response.status}")
                    return False
                print(f"Login successful. Redirect URL: {response.headers.get('Location')}")
                return True
        except Exception as e:
            print(f"An error occurred during login: {str(e)}")
            return False

    async def check_for_updates(self, username, password):
        """Check for new updates on the LMS portal"""
        login_successful = await self.login(username, password)
        if not login_successful:
            print(f"Failed to login for user: {username}")
            return None

        session = await self.get_session()
        try:
            async with session.get(CALENDAR_URL) as response:
                if response.status != 200:
                    print(f"Failed to access calendar page. Status code: {response.status}")
                    return None
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                events = soup.find_all(class_='event')

                if not events:
                    print("No events found.")

                new_items = []
                for event in events:
                    date = event.select_one('.row .col-11')
                    name = event.select_one('.name')
                    
                    date_text = date.text.strip() if date else 'Unknown Date'
                    name_text = name.text.strip() if name else 'Unknown Event'

                    # Filter out attendance events
                    if 'attendance' not in name_text.lower():
                        new_items.append(f"📅 **{date_text}**\n📌 {name_text}")

                return new_items
        except Exception as e:
            print(f"An error occurred while checking for updates: {str(e)}")
            return None

    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()

portal_monitor = PortalMonitor()

def migrate_database():
    """Migrate the database to use encrypted passwords"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Check if the old 'password' column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'password' in columns and 'encrypted_password' not in columns:
        print("Migrating existing data...")
        # Fetch all existing users
        cursor.execute('SELECT user_id, username, password FROM users')
        users = cursor.fetchall()
        
        # Add the encrypted_password column
        cursor.execute('ALTER TABLE users ADD COLUMN encrypted_password TEXT')
        
        # Migrate data
        for user in users:
            encrypted_password = db.cipher_suite.encrypt(user[2].encode()).decode()
            cursor.execute('UPDATE users SET encrypted_password = ? WHERE user_id = ?', (encrypted_password, user[0]))
        
        # Remove the old password column
        cursor.execute('CREATE TABLE users_new (user_id INTEGER PRIMARY KEY, username TEXT, encrypted_password TEXT)')
        cursor.execute('INSERT INTO users_new SELECT user_id, username, encrypted_password FROM users')
        cursor.execute('DROP TABLE users')
        cursor.execute('ALTER TABLE users_new RENAME TO users')
        
        conn.commit()
        print("Data migration completed.")
    
    conn.close()

@bot.event
async def on_ready():
    """Event handler for when the bot is ready"""
    print(f'{bot.user} has connected to Discord!')
    check_updates.start()

async def send_welcome_message(user):
    """Send a welcome message to a user"""
    welcome_message = (
        "👋 Welcome to the LMS Update Bot! Here are the available commands:\n\n"
        "🔹 `!register`: Start the registration process to receive LMS updates.\n"
        "🔹 `!force_check`: Manually check for LMS updates.\n"
        "🔹 `!bothelp`: Display this help message.\n\n"
        "To get started, use the `!register` command to set up your LMS credentials. "
        "After registration, you'll receive automatic updates every 30 minutes."
    )
    await user.send(welcome_message)

async def register_user(member):
    """Register a new user"""
    try:
        await member.send("Please enter your LMS username:")
        username_msg = await bot.wait_for('message', check=lambda m: m.author == member and isinstance(m.channel, discord.DMChannel), timeout=300)
        
        await member.send("Please enter your LMS password:")
        password_msg = await bot.wait_for('message', check=lambda m: m.author == member and isinstance(m.channel, discord.DMChannel), timeout=300)
        
        db.add_user(member.id, username_msg.content, password_msg.content)
        await member.send("You've been registered successfully! Checking for updates now...")
        
        # Perform an immediate check for the newly registered user
        updates = await portal_monitor.check_for_updates(username_msg.content, password_msg.content)
        if updates:
            embed = discord.Embed(title="🔔 New LMS Updates", color=0x00ff00)
            for update in updates:
                embed.add_field(name="", value=update, inline=False)
            await member.send(embed=embed)
        else:
            await member.send("No new updates found at the moment. You'll receive updates when they're available.")
    except asyncio.TimeoutError:
        await member.send("Registration timed out. Please try again later or use the !register command.")

@bot.command(name='register')
async def register_command(ctx):
    """Command to register a new user"""
    if isinstance(ctx.channel, discord.DMChannel):
        await register_user(ctx.author)
    else:
        await ctx.send("I've sent you a DM to start the registration process.")
        await register_user(ctx.author)

@bot.command(name='bothelp')
async def bothelp_command(ctx):
    """Command to display help information"""
    await send_welcome_message(ctx.author)

@tasks.loop(minutes=30)
async def check_updates():
    """Periodic task to check for updates"""
    users = db.get_all_users()
    for user_id, username, password in users:
        updates = await portal_monitor.check_for_updates(username, password)
        if updates:
            user = await bot.fetch_user(user_id)
            embed = discord.Embed(title="🔔 New LMS Updates", color=0x00ff00)
            for update in updates:
                embed.add_field(name="", value=update, inline=False)
            await user.send(embed=embed)

@check_updates.before_loop
async def before_check_updates():
    """Preparation before starting the update check loop"""
    await bot.wait_until_ready()
    await asyncio.sleep(60)  # Wait for 1 minute after bot is ready before first check

@bot.command(name='force_check')
async def force_check(ctx):
    """Command to force an immediate update check"""
    await ctx.send("Forcing an update check...")
    try:
        users = db.get_all_users()
        if not users:
            await ctx.send("No registered users found. Use the !register command to add users.")
            return
        await check_updates()
        await ctx.send("Update check completed.")
    except Exception as e:
        error_message = f"An error occurred during the update check: {str(e)}"
        print(error_message)
        await ctx.send(error_message)

@bot.event
async def on_command_error(ctx, error):
    """Error handler for bot commands"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Use !bothelp to see available commands.")
    else:
        print(f"An error occurred: {error}")
        await ctx.send(f"An error occurred: {error}")

@bot.command(name='remove_all_users')
@commands.is_owner()  # Ensure only the bot owner can use this command
async def remove_all_users(ctx):
    """Command to remove all user data (owner only)"""
    db.remove_all_users()
    await ctx.send("All user data has been removed.")

async def main():
    """Main function to run the bot"""
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    # Migrate database before removing all users
    migrate_database()
    
    # Initialize the database
    db = Database('users.db')
    
    # Remove all current user data
    db.remove_all_users()
    print("All user data has been removed.")
    
    asyncio.run(main())
