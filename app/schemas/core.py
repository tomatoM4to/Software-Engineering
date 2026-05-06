from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

ProductCode = Literal["01", "03", "08", "22", "29"]


class RunMode(StrEnum):
    """실행모드, 실전투자(PROD)과 모의투자(PAPER) 구분용 Enum"""

    PROD = "prod"
    PAPER = "vps"


class KisEnvironment(BaseModel):
    """RunMode과 ProductCode에 따라 필요한 인증 정보와 URL을 담는 환경 객체"""

    my_app: str
    my_sec: str
    my_acct: str
    my_prod: ProductCode
    my_htsid: str
    my_token: str
    my_url: str
    my_url_ws: str


class KisTokenResponse(BaseModel):
    """토큰 발급 API 응답 모델"""

    access_token: str
    access_token_token_expired: str


class KisConfig(BaseModel):
    """kis_devlp.yaml 파일의 내용을 담는 시스템 설정값"""

    my_app: str
    my_sec: str
    paper_app: str | None = None
    paper_sec: str | None = None
    my_htsid: str
    my_acct_stock: str
    my_acct_future: str | None = None
    my_paper_stock: str | None = None
    my_paper_future: str | None = None
    my_prod: ProductCode
    prod: str
    ops: str
    vps: str
    vops: str
    my_token: str
    my_agent: str

    def _require(self, key: str, value: str | None) -> str:
        if value is None or value == "":
            raise ValueError(f"kis_devlp.yaml required key is missing or empty: {key}")
        return value

    def app_credentials(self, mode: RunMode) -> tuple[str, str]:
        if mode == RunMode.PROD:
            app = self.my_app
            sec = self.my_sec
            app_key_name = "my_app"
            sec_key_name = "my_sec"
        else:
            app = self.paper_app
            sec = self.paper_sec
            app_key_name = "paper_app"
            sec_key_name = "paper_sec"
        return self._require(app_key_name, app), self._require(sec_key_name, sec)

    def select_account(self, mode: RunMode, product: ProductCode) -> str:
        if mode == RunMode.PROD:
            account_by_product = {
                "01": self.my_acct_stock,
                "03": self.my_acct_future,
                "08": self.my_acct_future,
                "22": self.my_acct_stock,
                "29": self.my_acct_stock,
            }
        else:
            account_by_product = {
                "01": self.my_paper_stock,
                "03": self.my_paper_future,
            }
        my_acct = account_by_product.get(product)
        return self._require(
            f"account for mode={mode.value}, product={product}", my_acct
        )

    def api_url(self, mode: RunMode) -> str:
        return self._require(mode.value, getattr(self, mode.value, None))

    def ws_url(self, mode: RunMode) -> str:
        return (self.ops if mode == RunMode.PROD else self.vops) or ""

    def to_environment(
        self, mode: RunMode, product: ProductCode, token_key: str
    ) -> KisEnvironment:
        my_app, my_sec = self.app_credentials(mode)
        return KisEnvironment(
            my_app=my_app,
            my_sec=my_sec,
            my_acct=self.select_account(mode, product),
            my_prod=product,
            my_htsid=self.my_htsid,
            my_token=token_key,
            my_url=self.api_url(mode),
            my_url_ws=self.ws_url(mode),
        )
