# Railway Hosting Manager Bot

Telegram bot for hosting Python bots on Railway.app with user management.

## Features
- Multi-user hosting system
- Owner activation panel (paid system)
- File manager (upload/download/delete)
- Bot control (start/stop/restart)
- System monitoring (RAM, CPU, Disk)
- SQLite database

## Setup on Railway

1. Create new project on Railway
2. Connect GitHub repo or upload files
3. Add environment variable (optional): none needed (token is hardcoded)
4. Deploy

## Owner Commands (ID: 6330128098)
- Click "Owner Panel" → "Activate User"
- Enter: User ID, RAM (MB), Disk (MB), Days
- User gets activated automatically

## User Usage
1. Start bot: /start
2. Wait for owner activation
3. Upload bot.py and requirements.txt
4. Control Panel → Start Bot

## File Structure
```
main.py          - Bot code
requirements.txt - Dependencies
railway.json     - Railway config
Dockerfile       - Container config
data/            - SQLite + user files
```

## Important
- Each user gets isolated folder in data/users/<user_id>/
- bot.py is the entry point for user bots
- requirements.txt auto-installs on start
- Restart = stop + start (reloads code)
