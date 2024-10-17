# LMS Discord Bot

This Discord bot automatically notifies users about updates on their college LMS (Learning Management System), specifically focusing on assignments, labs, quizzes, and other important events while filtering out attendance-related notifications.

## Features

- Secure storage of user credentials using encryption
- Automatic notifications for new LMS updates
- Manual update checking
- Filtering of attendance-related events
- Easy registration process via Discord DMs

## Prerequisites

Before you begin, ensure you have met the following requirements:

* Python 3.7 or later
* A Discord account and a registered Discord application/bot
* Access to the LMS you want to monitor

## Installation

1. Clone this repository:   ```
   git clone https://github.com/yourusername/lms-discord-bot.git
   cd lms-discord-bot   ```

2. Install the required packages:   ```
   pip install -r requirements.txt   ```

3. Set up your Discord bot token in a `.env` file:   ```
   DISCORD_TOKEN=your_discord_bot_token_here   ```

## Configuration

1. Update the `PORTAL_URL`, `LOGIN_URL`, and `CALENDAR_URL` variables in `discord_bot.py` if your LMS uses different URLs.

2. Customize the update check interval by modifying the `@tasks.loop(minutes=30)` decorator in `discord_bot.py`.

## Usage

1. Run the bot:   ```
   python discord_bot.py   ```

2. Invite the bot to your Discord server using the OAuth2 URL generated in the Discord Developer Portal.

3. Users can register with the bot using the following command in a Discord channel or DM:   ```
   !register   ```

4. Other available commands:
   - `!force_check`: Manually trigger an update check
   - `!bothelp`: Display help information

## Security

- User credentials are stored securely using encryption.
- The encryption key is stored in `encryption_key.key`. Keep this file secure and back it up safely.

## Customization

You can customize the bot's behavior by modifying the following:

- Event filtering logic in the `check_for_updates` method of the `PortalMonitor` class
- Update check interval in the `@tasks.loop` decorator
- Command prefixes and names in the `discord_bot.py` file

## Troubleshooting

If you encounter any issues:

- Ensure your Discord bot token is correct in the `.env` file
- Check if the LMS URLs are correct and accessible
- Verify that you have the necessary permissions in your Discord server

## Contributing

Contributions to improve the LMS Discord Bot are welcome. Please follow these steps:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/your-feature-name`)
3. Make your changes
4. Commit your changes (`git commit -am 'Add some feature'`)
5. Push to the branch (`git push origin feature/your-feature-name`)
6. Create a new Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This bot is for educational purposes only. Ensure you have permission to access and monitor your LMS using automated tools.
