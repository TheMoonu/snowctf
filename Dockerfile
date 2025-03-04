FROM python:3.11-slim
ARG debian_host=mirrors.ustc.edu.cn
ARG pip_index_url=https://mirrors.tencent.com/pypi/simple
ARG pip_trusted_host=mirrors.tencent.com
ENV PYTHONUNBUFFERED=1
WORKDIR /opt/cloud/snowctf

# 替换系统源并安装依赖（合并多个RUN命令减少层数）
RUN sed -i "s/deb.debian.org/${debian_host}/g" /etc/apt/sources.list.d/debian.sources \
    && pip install --upgrade pip supervisor gunicorn --index-url $pip_index_url --trusted-host $pip_trusted_host --root-user-action=ignore \
    && apt-get update && apt-get install -y \
       default-libmysqlclient-dev \
       build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime

# 安装Python依赖
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt --index-url $pip_index_url --trusted-host $pip_trusted_host --root-user-action=ignore

# 创建日志目录
RUN mkdir -p log && \
    chmod -R 755 log && \
    chown -R www-data:www-data log

# 复制项目文件到容器中
COPY . .

# 设置文件和目录权限（合并多个权限设置减少层数）
RUN chmod -R 755 /opt/cloud/snowctf \
    && chown -R www-data:www-data /opt/cloud/snowctf \
    && find /opt/cloud/snowctf -name "*.py" -exec chmod 644 {} \; \
    && chmod 600 /opt/cloud/snowctf/snowctf/settings.py \
    && chown www-data:www-data /opt/cloud/snowctf/snowctf/settings.py

CMD ["supervisord", "-n", "-c", "supervisord.conf"]