import uuid
import requests
import urllib3

from config.settings import (
    GIGACHAT_API,
    GIGACHAT_AUTH_KEY,
    GIGACHAT_OAUTH,
    GIGACHAT_SCOPE,
    HTTP_TIMEOUT,
    MODEL,
)

urllib3.disable_warnings()


class BertaBrain:
    def __init__(self):
        self.token = None
        self.token_expires_at = 0

    def get_token(self):
        import time

        if self.token and time.time() < self.token_expires_at - 60:
            return self.token

        if not GIGACHAT_AUTH_KEY:
            raise RuntimeError("GIGACHAT_AUTH_KEY не задан в .env")

        response = requests.post(
            GIGACHAT_OAUTH,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": "Basic " + GIGACHAT_AUTH_KEY,
            },
            data={"scope": GIGACHAT_SCOPE},
            verify=False,
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Ошибка получения GigaChat токена: HTTP {response.status_code}"
            )

        data = response.json()
        self.token = data["access_token"]
        self.token_expires_at = int(data.get("expires_at") or (time.time() + 1800))
        return self.token

    def ask(self, messages, functions=None):
        import time
        from tools.monitoring import (
            record_ai_request_start,
            record_ai_request_success,
            record_ai_request_error,
        )

        record_ai_request_start()
        t0 = time.time()
        token = self.get_token()
        payload = {"model": MODEL, "messages": messages}
        if functions:
            payload["functions"] = functions
            payload["function_call"] = "auto"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + token,
        }

        try:
            response = requests.post(
                GIGACHAT_API + "/chat/completions",
                headers=headers,
                json=payload,
                verify=False,
                timeout=HTTP_TIMEOUT,
            )

            if response.status_code == 401:
                self.token = None
                token = self.get_token()
                headers["Authorization"] = "Bearer " + token
                response = requests.post(
                    GIGACHAT_API + "/chat/completions",
                    headers=headers,
                    json=payload,
                    verify=False,
                    timeout=HTTP_TIMEOUT,
                )

            if response.status_code != 200:
                record_ai_request_error(
                    error=response.text[:500],
                    http_status=response.status_code,
                )
                raise RuntimeError(
                    f"Ошибка GigaChat: HTTP {response.status_code}: {response.text[:1500]}"
                )

            data = response.json()
            elapsed = time.time() - t0
            usage = data.get("usage") or {}
            record_ai_request_success(elapsed=elapsed, usage=usage)
            return data
        except RuntimeError:
            raise
        except Exception as exc:
            record_ai_request_error(error=str(exc)[:500])
            raise
