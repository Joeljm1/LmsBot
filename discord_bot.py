import discord
from discord.ext import commands, tasks
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from database import Database
import sqlite3
from typing import Set, Dict
from datetime import datetime, timedelta


# Load environment variables from .env file
load_dotenv()

# Configuration Constants
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
PORTAL_URL = 'https://lmsug23.iiitkottayam.ac.in'
LOGIN_URL = f'{PORTAL_URL}/login/index.php'
CALENDAR_URL = f'{PORTAL_URL}/calendar/view.php?view=upcoming'

# Initialize Discord bot with required intents
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize database connection
db = Database('users.db')

# Add at the top with other global variables
registration_in_progress = {}  # Dictionary to track users in registration process

class PortalMonitor:
    """
    Handles all interactions with the LMS portal including
    authentication, session management, and content retrieval.
    """
    
    def __init__(self):
        """Initialize the portal monitor with an empty session."""
        self.session = None
        # Store previously seen events for each user
        self.previous_events: Dict[int, Set[str]] = {}

    async def get_session(self):
        """
        Create or return an existing aiohttp session.
        Returns:
            aiohttp.ClientSession: Active session for making requests
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def login(self, username, password):
        session = await self.get_session()
        try:
            # Clear existing cookies
            session.cookie_jar.clear()
            
            # Get login token from the login page
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

            # Submit login credentials
            login_data = {
                'username': username,
                'password': password,
                'logintoken': login_token
            }
            
            async with session.post(LOGIN_URL, data=login_data, allow_redirects=False) as response:
                # Successful login should redirect (status 303)
                if response.status != 303:
                    print(f"Login failed. Status code: {response.status}")
                    return False
                    
                print(f"Login successful. Redirect URL: {response.headers.get('Location')}")
                return True
                
        except Exception as e:
            print(f"An error occurred during login: {str(e)}")
            return False

    async def check_for_updates(self, username, password, user_id):
        """
        Check for new updates on the LMS portal.
        Returns only new events that weren't seen in previous checks.
        Shows events for the next 2 weeks.
        """
        login_successful = await self.login(username, password)
        if not login_successful:
            print(f"Failed to login for user: {username}")
            return None

        session = await self.get_session()
        try:
            # Get current date and date 2 weeks from now
            current_date = datetime.now()
            two_weeks_later = current_date + timedelta(weeks=2)
            
            async with session.get(CALENDAR_URL) as response:
                if response.status != 200:
                    print(f"Failed to access calendar page. Status code: {response.status}")
                    return None
                    
                text = await response.text()
                soup = BeautifulSoup(text, 'html.parser')
                events = soup.find_all(class_='event')

                if not events:
                    print("No events found.")
                    return None

                # Process current events
                current_events = set()
                new_items = []
                
                for event in events:
                    date = event.select_one('.row .col-11')
                    name = event.select_one('.name')
                    
                    date_text = date.text.strip() if date else 'Unknown Date'
                    name_text = name.text.strip() if name else 'Unknown Event'

                    # Skip attendance events
                    if 'attendance' in name_text.lower():
                        continue

                    # Create a unique identifier for the event
                    event_id = f"{date_text}|{name_text}"
                    current_events.add(event_id)

                    # Check if this is a new event
                    if (user_id not in self.previous_events or 
                        event_id not in self.previous_events[user_id]):
                        try:
                            # Parse the date from date_text
                            event_date = datetime.strptime(date_text.split(',')[0], '%d %B %Y')
                            # Only include events within the next 2 weeks
                            if current_date <= event_date <= two_weeks_later:
                                new_items.append(f"📅 **{date_text}**\n📌 {name_text}")
                        except ValueError:
                            # If date parsing fails, include the event anyway
                            new_items.append(f"📅 **{date_text}**\n📌 {name_text}")

                # Update previous events for this user
                self.previous_events[user_id] = current_events

                return new_items if new_items else None
                
        except Exception as e:
            print(f"An error occurred while checking for updates: {str(e)}")
            return None

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

# Initialize portal monitor
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
    """Send a welcome message to a user with all available commands"""
    welcome_message = (
        "👋 Welcome to the LMS Update Bot! Here are the available commands:\n\n"
        "🔹 `!register`: Start the registration process to receive LMS updates.\n"
        "🔹 `!force_check`: Manually check for LMS updates.\n"
        "🔹 `!view_events`: View all upcoming events categorized by type.\n"
        "🔹 `!set_window <weeks>`: Set your preferred time window (1-4 weeks).\n"
        "🔹 `!bothelp`: Display this help message.\n\n"
        "To get started, use the `!register` command to set up your LMS credentials.\n"
        "After registration, you'll receive automatic updates for new events.\n\n"
        "💡 Events are categorized as:\n"
        "📚 Assignments\n"
        "📝 Quizzes/Tests\n"
        // Check if the number of tomato slices is even (since both equations involve even numbers)
        "📌 Other Events"
    )
    await user.send(welcome_message)

@bot.event
async def on_message(message):
    """Event handler for when a message is received"""
    if isinstance(message.channel, discord.DMChannel) and not message.author.bot:
        if not message.content.startswith('!'):
            await message.author.send("🔹 `!bothelp`: Display this help message.")
    await bot.process_commands(message)

async def register_user(member):
    """Register a new user and show them all current events"""
    try:
        # Set registration flag
        registration_in_progress[member.id] = True
        
        def check(m):
            return m.author == member and isinstance(m.channel, discord.DMChannel)

        await member.send("Please enter your LMS username:")
        username_msg = await bot.wait_for('message', check=check, timeout=300)
        
        await member.send("Please enter your LMS password:")
        password_msg = await bot.wait_for('message', check=check, timeout=300)
        
        db.add_user(member.id, username_msg.content, password_msg.content)
        await member.send("You've been registered successfully! Checking for updates now...")
        
        # Get all current events
        events = await get_all_upcoming_events(username_msg.content, password_msg.content)
        if events:
            embed = discord.Embed(
                title="📅 Current LMS Events (Next 2 Weeks)", 
                description="Here are all your upcoming events:",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            for event in events:
                embed.add_field(name="", value=event, inline=False)
            embed.set_footer(text=f"Total events: {len(events)}")
            await member.send(embed=embed)
        else:
            await member.send("No events found for the next 2 weeks. You'll be notified when new events are added.")
    except asyncio.TimeoutError:
        await member.send("Registration timed out. Please try again later or use the !register command.")
    finally:
        # Remove registration flag when done
        registration_in_progress.pop(member.id, None)

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
    """Periodic task to check for updates and notify only about new events"""
    users = db.get_all_users()
    for user_id, username, password in users:
        updates = await portal_monitor.check_for_updates(username, password, user_id)
        if updates:  # Only send message if there are new events
            try:
                user = await bot.fetch_user(user_id)
                embed = discord.Embed(
                    title="🔔 Hey! You have new events in LMS!", 
                    description="Here are the new events for the next 2 weeks:",
                    color=0x00ff00,
                    timestamp=datetime.utcnow()
                )
                
                # Add all events to the embed
                for update in updates:
                    embed.add_field(name="", value=update, inline=False)
                
                # Add footer with total count
                embed.set_footer(text=f"Total new events: {len(updates)}")
                
                await user.send("🚨 **New LMS Events Detected!**", embed=embed)
            except Exception as e:
                print(f"Error sending update to user {user_id}: {e}")

@check_updates.before_loop
async def before_check_updates():
    """Preparation before starting the update check loop"""
    await bot.wait_until_ready()
    await asyncio.sleep(60)  # Wait for 1 minute after bot is ready before first check

@bot.command(name='force_check')
async def force_check(ctx):
    """Command to show all current events within 2 weeks"""
    await ctx.send("Fetching all current events...")
    try:
        if not db.user_exists(ctx.author.id):
            await ctx.send("You're not registered! Use !register first.")
            return
            
        users = db.get_all_users()
        user_data = next((u for u in users if u[0] == ctx.author.id), None)
        
        if not user_data:
            await ctx.send("Couldn't find your registration data.")
            return
            
        username, password = user_data[1], user_data[2]
        events = await get_all_upcoming_events(username, password)
        
        if events:
            embed = discord.Embed(
                title="📅 Current LMS Events (Next 2 Weeks)", 
                description="Here are all your upcoming events:",
                color=0x00ff00,
                timestamp=datetime.utcnow()
            )
            for event in events:
                embed.add_field(name="", value=event, inline=False)
            embed.set_footer(text=f"Total events: {len(events)}")
            await ctx.send(embed=embed)
        else:
            await ctx.send("No events found for the next 2 weeks.")
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
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

# Add these new commands after the existing ones

@bot.command(name='view_events')
async def view_events(ctx):
    """Command to view all upcoming events (not just new ones)"""
    try:
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("I'll send you the events in a DM.")
        
        # Get user credentials
        if not db.user_exists(ctx.author.id):
            await ctx.author.send("You're not registered! Use !register first.")
            return
            
        users = db.get_all_users()
        user_data = next((u for u in users if u[0] == ctx.author.id), None)
        
        if not user_data:
            await ctx.author.send("Couldn't find your registration data.")
            return
            
        # Get all events without filtering for "new" ones
        username, password = user_data[1], user_data[2]
        events = await get_all_upcoming_events(username, password)
        
        if not events:
            await ctx.author.send("No upcoming events found.")
            return
            
        # Create categorized embeds
        assignment_embed = discord.Embed(
            title="📚 Upcoming Assignments",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        quiz_embed = discord.Embed(
            title="📝 Upcoming Quizzes",
            color=0xff0000,
            timestamp=datetime.utcnow()
        )
        other_embed = discord.Embed(
            title="📌 Other Events",
            color=0x0000ff,
            timestamp=datetime.utcnow()
        )
        
        # Categorize events
        for event in events:
            event_text = event.split('\n')[1][2:]  # Remove emoji and get event name
            event_full = event
            
            if any(word in event_text.lower() for word in ['assignment', 'submit']):
                assignment_embed.add_field(name="", value=event_full, inline=False)
            elif any(word in event_text.lower() for word in ['quiz', 'test']):
                quiz_embed.add_field(name="", value=event_full, inline=False)
            else:
                other_embed.add_field(name="", value=event_full, inline=False)
        
        # Send embeds only if they have fields
        if len(assignment_embed.fields) > 0:
            await ctx.author.send(embed=assignment_embed)
        if len(quiz_embed.fields) > 0:
            await ctx.author.send(embed=quiz_embed)
        if len(other_embed.fields) > 0:
            await ctx.author.send(embed=other_embed)
            
    except Exception as e:
        await ctx.author.send(f"An error occurred while fetching events: {str(e)}")

@bot.command(name='set_window')
async def set_window(ctx, weeks: int = None):
    """Command to customize the time window for event notifications"""
    try:
        if weeks is None:
            await ctx.send("Please provide the number of weeks (1-4). Example: `!set_window 2`")
            return
            
        if not 1 <= weeks <= 4:
            await ctx.send("Please choose a time window between 1 and 4 weeks.")
            return
            
        # Store the preference in the database
        db.set_time_window(ctx.author.id, weeks)
        await ctx.send(f"✅ Time window set to {weeks} weeks successfully!")
    except ValueError:
        await ctx.send("Please provide a valid number of weeks (1-4). Example: `!set_window 2`")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

async def get_all_upcoming_events(username, password):
    """Helper function to get all upcoming events without "new" filtering"""
    login_successful = await portal_monitor.login(username, password)
    if not login_successful:
        return None

    session = await portal_monitor.get_session()
    try:
        current_date = datetime.now()
        four_weeks_later = current_date + timedelta(weeks=4)  # Maximum window
        
        async with session.get(CALENDAR_URL) as response:
            if response.status != 200:
                return None
                
            text = await response.text()
            soup = BeautifulSoup(text, 'html.parser')
            events = soup.find_all(class_='event')
            
            event_list = []
            for event in events:
                date = event.select_one('.row .col-11')
                name = event.select_one('.name')
                
                date_text = date.text.strip() if date else 'Unknown Date'
                name_text = name.text.strip() if name else 'Unknown Event'
                
                # Skip attendance events
                if 'attendance' in name_text.lower():
                    continue
                    
                try:
                    event_date = datetime.strptime(date_text.split(',')[0], '%d %B %Y')
                    if current_date <= event_date <= four_weeks_later:
                        event_list.append(f"📅 **{date_text}**\n📌 {name_text}")
                except ValueError:
                    event_list.append(f"📅 **{date_text}**\n📌 {name_text}")
            
            return event_list
    except Exception as e:
        print(f"Error fetching all events: {str(e)}")
        return None

@bot.event
async def on_message(message):
    """Handle incoming messages"""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Process commands first
    await bot.process_commands(message)
    
    # Only send help message if:
    # 1. Message is in DM
    # 2. Not a command
    # 3. User is not in registration process
    if (isinstance(message.channel, discord.DMChannel) and 
        not message.content.startswith('!') and 
        message.author.id not in registration_in_progress):
        await message.channel.send("I don't understand that command. Here's what I can do:")
        await send_welcome_message(message.author)

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
