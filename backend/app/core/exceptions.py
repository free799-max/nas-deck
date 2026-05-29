"""业务异常定义。"""


class APIException(Exception):
    """业务 API 异常，会被全局处理器捕获并包装为标准响应格式。

    Attributes:
        message: 人类可读的错误描述
        status_code: HTTP 状态码
    """

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
