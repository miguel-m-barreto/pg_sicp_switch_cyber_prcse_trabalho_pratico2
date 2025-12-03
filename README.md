# Como fica o server.py a correr mesmo sem nenhuma instancia da VM ligada?

## 1. Criei um script de arranque no servidor (Na VM Gcloud)

sudo nano /usr/local/bin/greyscrape-server.sh

```
#!/bin/bash

cd /greyscrape/greyscrape
exec /usr/bin/python3 server.py
```

sudo chmod +x /usr/local/bin/greyscrape-server.sh

## 2. Criei um serviço systemd

sudo nano /etc/systemd/system/greyscrape.service

```
[Unit]
Description=GreyScrape Python Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/greyscrape-server.sh
WorkingDirectory=/greyscrape/greyscrape
Restart=always
RestartSec=3
User=postgrad_grupo
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

## 3. Run on startup e background

sudo systemctl daemon-reload
sudo systemctl enable greyscrape.service
sudo systemctl start greyscrape.service


## Ao alterar codigo

sudo systemctl restart greyscrape.service
sudo systemctl status greyscrape.service

```
Deve aparecer algo como:
Active: active (running)


Se aparecer “failed”, ver o erro com:
journalctl -u greyscrape.service -n 100 --no-pager
```