import os
from dotenv import load_dotenv
load_dotenv()
GIGACHAT_AUTH_KEY=os.getenv('GIGACHAT_AUTH_KEY','')
GIGACHAT_SCOPE=os.getenv('GIGACHAT_SCOPE','GIGACHAT_API_PERS')
GIGACHAT_API=os.getenv('GIGACHAT_API','https://api.giga.chat/v1')
GIGACHAT_OAUTH=os.getenv('GIGACHAT_OAUTH','https://ngw.devices.sberbank.ru:9443/api/v2/oauth')
MODEL=os.getenv('MODEL','GigaChat-2')
VERSION='0.2'
