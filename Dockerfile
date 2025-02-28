FROM python:3.11-slim
ARG debian_host=mirrors.ustc.edu.cn
ARG pip_index_url=https://mirrors.tencent.com/pypi/simple
ARG pip_trusted_host=mirrors.tencent.com
ENV PYTHONUNBUFFERED=1
WORKDIR /opt/cloud/snowctf

# 替换系统源，要注意这里不同版本的debian源文件不同
RUN sed -i "s/deb.debian.org/${debian_host}/g" /etc/apt/sources.list.d/debian.sources


RUN pip install --upgrade pip --root-user-action=ignore
# 安装sqlclient的依赖，slim镜像中缺少
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt --index-url $pip_index_url --trusted-host $pip_trusted_host --root-user-action=ignore
RUN mkdir -p log && \
    chmod -R 755 log && \
    chown -R www-data:www-data log


# 复制项目文件到容器中
COPY . .

# 设置文件和目录权限
RUN chmod -R 755 /opt/cloud/snowctf && \
    chown -R www-data:www-data /opt/cloud/snowctf 

# Python 源文件权限设置为 644（所有者可读写，其他用户可读）
RUN find /opt/cloud/snowctf -name "*.py" -exec chmod 644 {} \; && \
    chown -R www-data:www-data /opt/cloud/snowctf/**/*.py


# 配置文件权限设置为 600（仅所有者可读写，其他用户无权限）
RUN chmod 600 /opt/cloud/snowctf/snowctf/settings.py && \
    chown www-data:www-data /opt/cloud/snowctf/snowctf/settings.py
    


CMD ["supervisord", "-n", "-c", "supervisord.conf"]