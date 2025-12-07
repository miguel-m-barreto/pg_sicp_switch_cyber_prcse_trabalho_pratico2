# DEPENDENCIES

Para correr os scrapers é necessário instalar o Chrome (headless), o ChromeDriver e as bibliotecas Python usadas pelo Selenium.

## Instalar Google Chrome (headless)

```bash
cd /tmp
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get update
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
```

Alternativa: Chromium + ChromeDriver (via apt)
```bash
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-chromedriver
```

Instalar dependências Python
```bash
pip3 install selenium beautifulsoup4 lxml python-dotenv
```

Permissões do projeto (AMBIENTES ISOLADOS APENAS)

Necessário dar permissões totais ao diretório inteiro:
```bash
sudo chmod -R 777 /greyscrape
```

## SERVIÇO SYSTEMD para correr 24/7

sudo nano /etc/systemd/system/greyscrape.service

------

[Unit]
Description=GreyScrape Scraper Loop
After=network.target

[Service]
Type=simple
User=postgrad_grupo
WorkingDirectory=/greyscrape/greyscrape
ExecStart=/usr/bin/python3 /greyscrape/greyscrape/run_loop.py
Restart=always
RestartSec=10
StandardOutput=append:/greyscyape/logs/greyscrape.service.log
StandardError=append:/greyscrape/logs/greyscrape.service.err

[Install]
WantedBy=multi-user.target


---
Criar diretório de logs

sudo mkdir -p /greyscrape/logs
sudo chown -R postgrad_grupo:postgrad_grupo /greyscrape/logs

----

Ativar o serviço

sudo systemctl daemon-reload
sudo systemctl enable greyscrape.service
sudo systemctl start greyscrape.service


Monitorizar o scraper

Estado do serviço:
systemctl status greyscrape.service


Logs em tempo real:
journalctl -u greyscrape.service -f


Ou diretamente pelos ficheiros de log:
tail -f /greyscrape/logs/greyscrape.service.log