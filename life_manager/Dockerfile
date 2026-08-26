FROM ghcr.io/home-assistant/base:latest

RUN apk add --no-cache python3 py3-pip

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip3 install --break-system-packages -r /app/requirements.txt

COPY app /app
COPY migrations /app/migrations
COPY frontend /frontend
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
