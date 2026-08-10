import requests
import uuid
import urllib3

from config.settings import *

urllib3.disable_warnings()


class BertaBrain:

    def __init__(self):
        self.token = None


    def get_token(self):

        if self.token:
            return self.token


        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": "Basic " + GIGACHAT_AUTH_KEY
        }


        data = {
            "scope": GIGACHAT_SCOPE
        }


        response = requests.post(
            GIGACHAT_OAUTH,
            headers=headers,
            data=data,
            verify=False,
            timeout=30
        )


        if response.status_code != 200:

            raise RuntimeError(
                "Ошибка получения GigaChat токена:\n"
                + response.text
            )


        self.token = response.json()["access_token"]

        return self.token



    def ask(self, messages, functions=None):

        token = self.get_token()


        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + token
        }


        payload = {

            "model": MODEL,

            "messages": messages
        }


        # ВАЖНО:
        # Это возвращает старую логику БЕРТЫ
        # GigaChat получает список инструментов

        if functions:

            payload["functions"] = functions

            payload["function_call"] = "auto"



        response = requests.post(

            GIGACHAT_API + "/chat/completions",

            headers=headers,

            json=payload,

            verify=False,

            timeout=120
        )



        # если токен протух

        if response.status_code == 401:

            self.token = None

            token = self.get_token()

            headers["Authorization"] = (
                "Bearer " + token
            )


            response = requests.post(

                GIGACHAT_API + "/chat/completions",

                headers=headers,

                json=payload,

                verify=False,

                timeout=120
            )



        if response.status_code != 200:

            raise RuntimeError(

                "Ошибка GigaChat:\n"

                + str(response.status_code)

                + "\n"

                + response.text[:5000]

            )



        return response.json()
