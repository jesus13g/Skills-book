# Skills Book — imagen para el servidor de la organizacion.
#
# Sin dependencias: la app es solo stdlib de Python, asi que la imagen es
# python:slim + el codigo. Los datos (las skills) viven en /data/skills, que
# es un volumen: la imagen se puede recrear entera sin perder nada.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Skills Book" \
      org.opencontainers.image.description="Biblioteca de skills para agentes, en la LAN." \
      org.opencontainers.image.source="https://github.com/jesus13g/skills-book"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SKILLSBOOK_HOME=/data/skills \
    SKILLSBOOK_HOST=0.0.0.0 \
    SKILLSBOOK_PORT=8777 \
    SKILLSBOOK_NO_BROWSER=1 \
    SKILLSBOOK_STRICT_PORT=1 \
    SKILLSBOOK_ALLOW_PATH_IMPORT=0

WORKDIR /app

# El codigo de la app, y las skills de ejemplo aparte: sirven de semilla para
# la primera arrancada, pero nunca pisan lo que ya haya en el volumen.
COPY skillsbook/ /app/skillsbook/
COPY skills/ /opt/skillsbook/skills-semilla/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod +x /usr/local/bin/entrypoint.sh \
    && useradd --uid 1000 --user-group --home-dir /data --no-log-init skillsbook \
    && mkdir -p /data/skills \
    && chown -R skillsbook:skillsbook /data /opt/skillsbook

USER skillsbook
VOLUME ["/data"]
EXPOSE 8777

# /healthz no pide token, asi que la sonda funciona con o sin autenticacion.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request,os,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('SKILLSBOOK_PORT','8777')+'/healthz', timeout=4).status==200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python3", "-m", "skillsbook"]
