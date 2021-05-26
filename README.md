# cpb_vk-to-tg

Сбор постов из нескольких групп ВК с трансляцией в канал ТГ. С разбивкой постов по абзацам и подкачкой вложенных файлов (изображения, файлы, ссылки, 
видео(хромает)).

Для работы требует дополнительно файл settings.py вида:

token = ХХХХХХ # VK API app token
#[Telegram]
bot_token = XXXXX # Telegram Bot BotFather token
bitlytoken = ХХХХ # Bit.ly profile token (optional)
