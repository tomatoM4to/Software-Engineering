import asyncio
import logging
from collections import namedtuple

import requests
from core import kis_auth as ka
from schemas.core import KisTrId

logger = logging.getLogger(__name__)


class APIResp:
    def __init__(self, resp: requests.Response):
        self._resp = resp
        self._rescode = resp.status_code
        self._is_success = self._rescode == 200

        if self._is_success:
            # 헤더 파싱 (소문자 키만 추출)
            fld = {k: v for k, v in resp.headers.items() if k.islower()}
            self._header = namedtuple("header", fld.keys())(**fld)

            # 바디 파싱
            body_data = resp.json()
            self._body = namedtuple("body", body_data.keys())(**body_data)

            self._err_code = getattr(self._body, "msg_cd", "")
            self._err_message = getattr(self._body, "msg1", "")
        else:
            # HTTP 에러 발생 시 더미 객체 할당 (AttributeError 방지)
            class EmptyNode:
                def __getattr__(self, name):
                    return ""

            self._header = EmptyNode()
            self._body = EmptyNode()
            self._err_code = str(self._rescode)
            self._err_message = resp.text

    def get_res_code(self):
        return self._rescode

    def get_header(self):
        return self._header

    def get_body(self):
        return self._body

    def get_response(self):
        return self._resp

    def is_ok(self):
        if not self._is_success:
            return False
        return getattr(self._body, "rt_cd", "") == "0"

    def get_error_code(self):
        return self._err_code

    def get_error_message(self):
        return self._err_message

    def print_all(self):
        if not self._is_success:
            logger.error("=== ERROR RESPONSE ===")
            logger.error(
                "Status Code: %s | Message: %s", self._rescode, self._err_message
            )
            return

        logger.debug("<Header>")
        for x in self._header._fields:
            logger.debug("\t-%s: %s", x, getattr(self._header, x))
        logger.debug("<Body>")
        for x in self._body._fields:
            logger.debug("\t-%s: %s", x, getattr(self._body, x))

    def print_error(self, url: str = ""):
        logger.error(
            "Error Code: %s | rt_cd: %s | msg_cd: %s | msg1: %s | URL: %s",
            self._rescode,
            getattr(self._body, "rt_cd", "N/A"),
            self._err_code,
            self._err_message,
            url,
        )


# -------------------------------------------------------------------------
# 비동기 큐(Queue) 기반 KIS API 초당 20건 제한 제어 시스템
# -------------------------------------------------------------------------
_kis_queue: asyncio.PriorityQueue | None = None
_kis_worker_task: asyncio.Task | None = None
_kis_task_counter: int = 0


async def start_kis_worker():
    """
    FastAPI Lifespan이나 앱 초기화 시점에 호출되는 워커 실행 함수.
    """
    global _kis_queue, _kis_worker_task
    if _kis_queue is None:
        _kis_queue = asyncio.PriorityQueue()
        _kis_worker_task = asyncio.create_task(_kis_request_consumer())
        logger.info(
            "[KIS Async Worker] Started background worker for API rate limiting (20 req/s)."
        )


async def _kis_request_consumer():
    """
    큐에서 이벤트를 꺼내 비동기(쓰레드풀)로 API를 요청하고,
    무조건 0.05초 대기하여 Rate Limit을 방어합니다.
    """
    while True:
        try:
            item = await _kis_queue.get()
            priority, _counter, payload = item
            future, request_kwargs = payload

            try:
                # 동기 requests가 이벤트 루프를 블로킹하지 않도록 분리 실행
                res = await asyncio.to_thread(_do_sync_fetch, **request_kwargs)
                if not future.done():
                    future.set_result(res)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)
            finally:
                _kis_queue.task_done()

            # 초당 20건 제한 완충 버퍼 대기
            await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            logger.info("[KIS Async Worker] Worker task cancelled.")
            break
        except Exception as e:
            logger.error("[KIS Async Worker] Unexpected error in consumer loop: %s", e)


def _do_sync_fetch(
    api_url: str,
    ptr_id: str | KisTrId,
    tr_cont: str,
    params: dict,
    append_headers: dict = None,
    post_flag: bool = False,
    hash_flag: bool = True,
) -> APIResp:
    """백그라운드 워커에서 실제 통신을 수행하는 동기 함수"""
    url = f"{ka.get_kis_env().my_url}{api_url}"
    headers = ka.get_base_header()

    tr_id = ptr_id.value if isinstance(ptr_id, KisTrId) else ptr_id
    if tr_id[0] in ("T", "J", "C") and ka.is_paper_trading():
        tr_id = "V" + tr_id[1:]

    headers.update({"tr_id": tr_id, "custtype": "P", "tr_cont": tr_cont})

    if append_headers:
        headers.update(append_headers)

    if ka._debug:
        logger.debug(
            "< Sending Info >\nURL: %s, TR: %s\n<header>\n%s\n<body>\n%s",
            url,
            tr_id,
            headers,
            params,
        )

    if post_flag:
        res = requests.post(url, headers=headers, json=params, timeout=10)
    else:
        res = requests.get(url, headers=headers, params=params, timeout=10)

    ar = APIResp(res)

    if not ar.is_ok():
        logger.error("Error Code : %s | %s", res.status_code, res.text)
    elif ka._debug:
        ar.print_all()

    return ar


async def async_url_fetch(
    api_url: str,
    ptr_id: str | KisTrId,
    tr_cont: str,
    params: dict,
    append_headers: dict = None,
    post_flag: bool = False,
    hash_flag: bool = True,
    priority: int = 5,
) -> APIResp:
    """
    라우터/서비스 계층에서 호출할 비동기(async) API.
    요청 정보와 약속 어음(Future)을 Queue에 넣고 대기합니다.
    """
    global _kis_queue, _kis_task_counter
    if _kis_queue is None:
        await start_kis_worker()

    loop = asyncio.get_running_loop()
    future = loop.create_future()
    request_kwargs = {
        "api_url": api_url,
        "ptr_id": ptr_id,
        "tr_cont": tr_cont,
        "params": params,
        "append_headers": append_headers,
        "post_flag": post_flag,
        "hash_flag": hash_flag,
    }

    _kis_task_counter += 1
    # 큐 탑승 (priority가 낮을수록 우선 처리)
    await _kis_queue.put((priority, _kis_task_counter, (future, request_kwargs)))

    # 응답이 도착할 때까지 비동기 대기
    return await future
