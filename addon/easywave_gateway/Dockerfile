ARG BUILD_FROM
FROM ${BUILD_FROM}

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

COPY gateway.py identification.py catalogue.py registry.json tx_timing.json run.sh /app/
RUN chmod 0755 /app/run.sh

CMD ["/app/run.sh"]
