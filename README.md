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


--------------------------


Cenários

### 1. Mudar só o scraper (scrapers/…)

run_loop.py continua igual.

O serviço fica a correr.
No próximo ciclo, quando ele fizer novo subprocess.run(...), já vai usar o código NOVO do scraper.
Não é obrigatório parar o serviço; é relativamente seguro.

### 2. Mudar o run_loop.py

O processo que já está em memória continua com a versão antiga.
O novo código só entra em ação quando fizer:

sudo systemctl restart greyscrape.service


Se não reiniciar, ele continua a correr com a versão anterior.

### 3. Mudar paths / nome de ficheiros

Se apagar ou mexer em /greyscrape/greyscrape/run_loop.py ou no script que ele chama, na próxima execução vai falhar.

O serviço não “morre” por causa da unit, mas o Python vai dar erro.

Mudar o próprio .service no repo

Se tiver o ficheiro greyscrape.service versionado e o alterar, tem de se fazer outra vez:

sudo cp greyscrape.service /etc/systemd/system/greyscrape.service
sudo systemctl daemon-reload
sudo systemctl restart greyscrape.service

### 4. dar permissão à pasta logs

```
sudo chown -R postgrad_grupo:postgrad_grupo /greyscrape/greyscrape/scrapers/auchan/logs
```

ou 

```
sudo chmod -R u+rwX /greyscrape/greyscrape/scrapers/auchan/logs
```