# LMS Discord Bot - Technical Details

This document provides a detailed technical overview of the LMS Discord Bot project.

## Project Structure

The project consists of the following main components:

1. `discord_bot.py`: The main script that runs the Discord bot and handles user interactions.
2. `database.py`: Manages the SQLite database for storing user credentials securely.
3. `requirements.txt`: Lists all the Python dependencies required for the project.
4. `.env`: Stores environment variables (not included in the repository for security reasons).
5. `encryption_key.key`: Stores the encryption key for securing user passwords.

## Key Technologies

- Python 3.7+
- discord.py: For creating and managing the Discord bot
- aiohttp: For asynchronous HTTP requests to the LMS portal
- BeautifulSoup4: For parsing HTML responses from the LMS portal
- SQLite: For local database storage
- cryptography: For encrypting and decrypting user passwords

## Core Functionality

### 1. Discord Bot (discord_bot.py)

The Discord bot is the main interface for users. It handles commands, user registration, and periodic update checks.

Key features:
- User registration via DM
- Manual update checks
- Automatic periodic update checks (every 30 minutes)
- Secure storage of user credentials

### 2. Database Management (database.py)

This module handles all database operations, including:
- Adding new users
- Retrieving user information
- Encrypting and decrypting user passwords
- Database migrations (if needed)

### 3. LMS Portal Interaction (PortalMonitor class in discord_bot.py)

This class is responsible for interacting with the LMS portal:
- Logging in to the LMS portal
- Checking for new updates
- Parsing the calendar page for relevant events

## Workflow

1. User Registration:
   - User initiates registration with `!register` command
   - Bot prompts for username and password via DM
   - Credentials are encrypted and stored in the database

2. Update Checking:
   - Periodic task runs every 30 minutes
   - For each registered user:
     - Log in to LMS portal
     - Fetch and parse the calendar page
     - Filter out irrelevant events (e.g., attendance)
     - Send Discord message if new updates are found

3. Manual Update Check:
   - User can force an immediate update check with `!force_check` command
   - Follows the same process as the periodic check

## Security Considerations

- User passwords are encrypted before storage using Fernet symmetric encryption
- The encryption key is stored separately in `encryption_key.key`
- Environment variables (e.g., Discord token) are stored in a `.env` file (not included in the repository)
- The bot uses Discord's DM feature for sensitive information exchange

## Deployment Considerations

- Ensure Python 3.7+ is installed on the deployment environment
- Install dependencies: `pip install -r requirements.txt`
- Set up the `.env` file with the Discord bot token
- Generate an encryption key and store it in `encryption_key.key`
- Run the bot: `python discord_bot.py`

## Future Improvements

- Implement a more robust error handling and logging system
- Add support for multiple LMS portals
- Implement user-specific settings (e.g., update frequency, notification preferences)
- Add unit tests for critical components
- Consider using a more scalable database solution for larger deployments
