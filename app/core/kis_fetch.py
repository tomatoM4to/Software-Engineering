import asyncio
import logging
from collections import namedtuple
from typing import Optional, Any

import requests
from core import kis_auth as ka
from schemas.core import KisTrId
from core.kis_cache import kis_cache

logger = logging.getLogger(__name__)


class APIResp:
    """
    한국투자증권(KIS) API의 응답을 표준화하여 처리하는 클래스 (Slim Version).
    성공 여부 판단과 바디 데이터 접근(namedtuple) 기능에 집중합니다.
    """

    def __init__(self, resp: Optional[requests.Response] = None, data: Optional[dict] = None):
        """
        APIResp 인스턴스를 초기화합니다.
        
        Args:
            resp (requests.Response, optional): 실제 네트워크 통신을 통해 받은 응답 객체.
            data (dict, optional): 캐시 시스템으로부터 받은 응답 데이터 딕셔너리.
        """
        self._is_success = False
        self._body_dict = {}
        self._err_msg = ""

        if resp is not None:
            self._rescode = resp.status_code
            self._is_success = (self._rescode == 200)
            if self._is_success:
                try:
                    self._body_dict = resp.json()
                    self._err_msg = self._body_dict.get("msg1", "")
                except Exception:
                    self._is_success = False
                    self._err_msg = "Failed to parse JSON response"
            else:
                self._err_msg = resp.text
        elif data is not None:
            self._rescode = 200
            self._is_success = True
            self._body_dict = data
            self._err_msg = data.get("msg1", "Success")
        else:
            self._rescode = 500
            self._is_success = False
            self._err_msg = "No response or data provided"

        # namedtuple로 변환 (기존 .get_body().field 접근 호환성 유지)
        if self._body_dict:
            self._body = namedtuple("body", self._body_dict.keys())(**self._body_dict)
        else:
            self._body = self._set_empty()

    def _set_empty(self):
        """필드 접근 시 AttributeError 방지를 위한 빈 객체 반환"""
        class Empty:
            def __getattr__(self, name): return ""
        return Empty()

    @staticmethod
    def from_cache(data: dict):
        """캐시 데이터로부터 APIResp 객체를 생성합니다."""
        return APIResp(data=data)

    def get_body(self):
        """namedtuple로 변환된 응답 바디 객체를 반환합니다."""
        return self._body

    def is_ok(self):
        """성공 여부(HTTP 200 및 rt_cd '0')를 반환합니다."""
        if not self._is_success:
            return False
        return str(self._body_dict.get("rt_cd", "0")) == "0"

    def get_error_message(self):
        """에러 메시지(msg1 또는 HTTP 응답 텍스트)를 반환합니다."""
        return self._err_msg

    def print_all(self):
        """디버깅을 위해 응답 바디를 로그에 출력합니다."""
        logger.debug(f"<APIResp Body> {self._body_dict}")



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

    ar = APIResp(resp=res)

    if not ar.is_ok():
        logger.error("Error Code : %s | %s", res.status_code, res.text)
    elif ka._debug:
        ar.print_all()

    return ar


async def async_cache_fetch(
    ptr_id: str | KisTrId,
    params: dict,
) -> APIResp:
    """
    [사용자 전용 Fast Path]
    큐를 전혀 타지 않고 오직 캐시만 확인
    """
    tr_id = ptr_id.value if isinstance(ptr_id, KisTrId) else ptr_id
    
    cached_data = await kis_cache.get_from_cache(tr_id, params)
    if cached_data:
        return APIResp.from_cache(cached_data)

    # 캐시에 데이터가 없으면 즉시 에러 반환 (대기 없음)
    return APIResp(data={"rt_cd": "7", "msg_cd": "CACHE_MISS", "msg1": "No cached data available"})


async def async_url_fetch(
    api_url: str,
    ptr_id: str | KisTrId,
    tr_cont: str,
    params: dict,
    append_headers: dict = None,
    post_flag: bool = False,
    hash_flag: bool = True,
    priority: int = 5,
    bypass_cache: bool = False,
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

