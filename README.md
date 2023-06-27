# TTS voise bot

```bash
pip install -r requirements.txt
```

```bash
sudo cp camera-bot.service /etc/systemd/system/voice-bot.service
sudo systemctl daemon-reload
sudo systemctl enable voice-bot.service
sudo systemctl start voice-bot.service
```

### check status
```bash
sudo systemctl status voice-bot
```