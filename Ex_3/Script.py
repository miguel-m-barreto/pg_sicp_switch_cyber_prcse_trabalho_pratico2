wsl --install
cd \\wsl$\Ubuntu\home\duarte

duarte@DESKTOP-DC5KNGJ:~$ sudo apt update && sudo apt install -y \
>   libimage-exiftool-perl \
>   pngcheck \
>   binutils \
  binwal>   binwalk \
>   ruby ruby-dev \
>   steghide \
>   imagemagick \
>   zbar-tools

duarte@DESKTOP-DC5KNGJ:~$ pngcheck -v PRCSE-C2.png
zlib warning:  different version (expected 1.2.13, using 1.3)

File: PRCSE-C2.png (862251 bytes)
  chunk IHDR at offset 0x0000c, length 13
    960 x 600 image, 24-bit RGB, non-interlaced
  chunk IDAT at offset 0x00025, length 65536
    zlib: deflated, 32K window, default compression
  chunk IDAT at offset 0x10031, length 65536
  chunk IDAT at offset 0x2003d, length 65536
  chunk IDAT at offset 0x30049, length 65536
  chunk IDAT at offset 0x40055, length 65536
  chunk IDAT at offset 0x50061, length 65536
  chunk IDAT at offset 0x6006d, length 65536
  chunk IDAT at offset 0x70079, length 65536
  chunk IDAT at offset 0x80085, length 65536
  chunk IDAT at offset 0x90091, length 65536
  chunk IDAT at offset 0xa009d, length 65536
  chunk IDAT at offset 0xb00a9, length 65536
  chunk IDAT at offset 0xc00b5, length 65536
  chunk IDAT at offset 0xd00c1, length 10070
  chunk IEND at offset 0xd2823, length 0
No errors detected in PRCSE-C2.png (16 chunks, 50.1% compression).

A) Esta análise diz nos que o ficheiro está estruturalmente correto e não contém chunks anormais. Cada chunk pode conter dados da imagem,metadados e mensagens ocultas. O ficheiro também não tem transparêncoa, assim não tendo canal alpha, que é onde é costume esconderem mensagens. Assim sendo, a mensagem deve estar nos Least Significant Bytes. Se tivesse canal Alpha, o output seria algo do género:
960 x 600 image, 32-bit RGBA, non-interlaced

B) Sendo que um ficheiro PNG é quase todo binário, ou seja, chdio de números, se alguém coloco uma mensagem em texto ela ficará lá em Bytes ASCII, logo o strings vai percorrer o ficheiro e encontrar qualquer seqiência de texto com mais de 4 caractgeres seguidos.
Pela execucao normal como poidemos ver na captura de ecra, nada de especial se denota.

C) verificar ficheiros embutidos

binwalk PRCSE-C2.png
binwalk -e PRCSE-C2.png

Fazemos estes comandos para vericicar se existem alguns ficheiros embutidos, ou seja comprimidos, dentro do nosso ficheiro. Verifica-se que efetivamente existem dados comprimidos depois do início, mas isto é normal num ficheiro .png porque os IDAT chunks contêm dados comprimidos. O ficheiro PNG nao armazena todos os pixeis de uma vez, divide os pixeis em blocos chamados chuncks, cada chuck tendo um tipo, comprimento, dados e crc. o idat, image data, Contém os pixels reais da imagem, mas comprimidos usando zlib/deflate. Para reconstruir a imagem, o software descomprime todos os IDAT chunks na ordem correta e monta a imagem final.

d) para este passo:

sudo apt update
sudo apt install ruby ruby-dev build-essential

sudo gem install zsteg

Cada pixel de uma imagem tem tres bits principias, vermelho R, verde G e azul B. cada cor e armazenada com 8 bits, 0-255. o least Significant bit é o último bit de cada cor, que afeta muito pouco a cor percebida. a mensagem escondida foi convertida para código biná«rio, e escondiidas nesses bits mais pequneos.

lemos todos os pixeis da imagem com zsteg, que analisou cada canal de cor, vericicou cada bitplane (cada posicao de bit, do menos ao mais signfdiicativo), e tentou se reconstruir texto legível de ficheiros escondidos.

No output vemos:

b1 → primeiro bit (menos significativo) de cada cor.

rgb → todos os canais de cor analisados juntos.

lsb → indica que os dados estão escondidos no bit menos importante.

text → zsteg identificou que os bits formam texto legível.

xy → significa que a análise foi feita por coordenadas de pixel, mas não precisamos disso para o relatório.

Verificou-se então que a mensagem estava encriptada, e recorrendo ao website cuberchef percebeu-se que a mensagem utilixava um cifra ROT13, que é uma cifra simples onde cada letra é substituída por outra 13 posições depois no alfabeto.

--resumo lsb--

cada pixel rgb tem 3 bytes

R: 1 0 0 0 1 0 0 1 

G: 1 1 0 0 1 1 0 0 - o bit mais a direita é o lsb

B: 0 1 0 0 1 1 0 0


e ao longo dos pixeis os bits agrupam se e ganham sentido.


-------------A MENSAGEM FINAL É:---------------------

congratulationsthisisprcsehiddenmessage