import copy
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml
from schemas.core import (
    KisConfig,
    KisEnvironment,
    KisTokenResponse,
    ProductCode,
    RunMode,
)

logger = logging.getLogger(__name__)

# config_root = ~/Software-Engineering
config_root = Path(__file__).resolve().parent.parent.parent


def _get_token_path(now: datetime | None = None) -> Path:
    """호출 시점 날짜 기준으로 Path 객체 ~/Software-Engineering/KISYYYYMMDD 반환"""
    current = now or datetime.today()
    return config_root / f"KIS{current.strftime('%Y%m%d')}"


with open(os.path.join(config_root, "kis_devlp.yaml"), encoding="utf-8") as f:
    _kis_cfg: KisConfig = KisConfig.model_validate(yaml.safe_load(f))


"""
_kis_env: 토큰, 앱키, 스크릿키, 계좌번호, 접속 URL 등
_is_paper: 모의투자, 실전투자 구분, 기본값 False(실전투자)
_smart_sleep = 최소 대기 시간
"""
_kis_env: KisEnvironment | None = None
_debug = False
_is_paper = False
_smart_sleep = 0.05

_base_headers = {
    "Content-Type": "application/json",
    "Accept": "text/plain",
    "charset": "UTF-8",
    "User-Agent": _kis_cfg.my_agent,
}


def read_token() -> str | None:
    """호출 시점 날짜 기준으로 KIS<DATE> 파일에서 토큰값 반환

    Returns:
        str | None: 유효한 토큰값 또는 None (파일이 없거나, 토큰이 만료된 경우, 또는 에러 발생 시)
    """
    try:
        token_path = _get_token_path()
        if not token_path.exists():
            return None

        with open(token_path, encoding="UTF-8") as f:
            tkg_tmp = yaml.load(f, Loader=yaml.FullLoader)

        exp_dt = datetime.strftime(tkg_tmp["valid-date"], "%Y-%m-%d %H:%M:%S")
        now_dt = datetime.today().strftime("%Y-%m-%d %H:%M:%S")

        # 저장된 토큰 만료일자 체크 (만료일시 > 현재일시 인경우 보관 토큰 리턴)
        if exp_dt > now_dt:
            return tkg_tmp["token"]
        else:
            return None
    except Exception:
        return None


def get_base_header():
    """_kis_env 설정값 기반, API 호출에 필요한 기본 header 값 반환"""
    return copy.deepcopy(_base_headers)


def auth(
    svr: str | RunMode = RunMode.PROD, product: ProductCode = _kis_cfg.my_prod, url=None
):
    """
    - access_token 발급
    - access_token 은 KIS<날짜>, _kis_env, _base_headers 의 Bearer 토큰으로 설정
    - 토큰 발급은 1일 1회 권장, 발급 시 알림톡 발송
    - 토큰 유효 시간은 발급 시점으로부터 24시간
    - 만료 6시간 이내 재발급 시 기존 토큰과 동일

    Args:
        svr: 트레이딩 모드 ("prod" 또는 "vps")
        product: 계좌상품코드 2자리 (예: 01/03/08/22/29)
        url: 인증 실패 시 알림톡 발송 URL (선택 사항)
    """
    mode = svr if isinstance(svr, RunMode) else RunMode(svr)

    appkey, appsecret = _kis_cfg.app_credentials(mode)

    saved_token: str | None = read_token()

    if saved_token is None:
        p = {
            "grant_type": "client_credentials",
            "appkey": appkey,
            "appsecret": appsecret,
        }
        token_url = f"{_kis_cfg.api_url(mode)}/oauth2/tokenP"
        res = requests.post(
            token_url, data=json.dumps(p), headers=copy.deepcopy(_base_headers)
        )
        if res.status_code == 200:
            token_response = KisTokenResponse.model_validate(res.json())
            my_tk = token_response.access_token
            my_exp = token_response.access_token_token_expired

            # save_token 인라인화
            token_path = _get_token_path()
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.touch(exist_ok=True)
            valid_date = datetime.strptime(my_exp, "%Y-%m-%d %H:%M:%S")
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(f"token: {my_tk}\n")
                f.write(f"valid-date: {valid_date}\n")
        else:
            logger.error("Get authentication token failed. Restart app and retry.")
            return
    else:
        # 기존 토큰 사용
        my_tk = saved_token

    # change_kis_env 인라인화
    global _is_paper, _smart_sleep, _kis_env
    if mode == RunMode.PROD:
        _is_paper = False
        _smart_sleep = 0.05
    elif mode == RunMode.PAPER:
        _is_paper = True
        _smart_sleep = 0.5

    _kis_env = _kis_cfg.to_environment(mode=mode, product=product, token_key=my_tk)

    _base_headers["authorization"] = f"Bearer {my_tk}"
    _base_headers["appkey"] = _kis_env.my_app if _kis_env else ""
    _base_headers["appsecret"] = _kis_env.my_sec if _kis_env else ""

    if _debug:
        logger.debug("[%s] => get AUTH Key completed!", datetime.now())


def get_kis_cfg() -> KisConfig:
    return _kis_cfg


def get_kis_env() -> KisEnvironment:
    return _kis_env


def is_paper_trading() -> bool:
    return _is_paper


def smart_sleep() -> None:
    """0.05초(PROD) 또는 0.5초(PAPER) 대기"""
    if _debug:
        logger.debug("[RateLimit] Sleeping %ss", _smart_sleep)
    time.sleep(_smart_sleep)
