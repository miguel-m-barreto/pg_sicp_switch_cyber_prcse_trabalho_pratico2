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