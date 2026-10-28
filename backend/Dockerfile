FROM docker:27-cli AS dockercli

FROM python:3.12-slim

WORKDIR /app

# Docker CLI 与 Compose 插件：后端通过挂载的 docker.sock 在宿主机上执行 docker compose / docker cp
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins

COPY requirements.txt .
RUN pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY . .

EXPOSE 5001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5001", "--proxy-headers"]
