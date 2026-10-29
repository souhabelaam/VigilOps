"""Publish the computed rates to the "rates" queue. Same code as the collector publisher."""
import json
import logging
import time

import pika
from pika.exceptions import AMQPError

log = logging.getLogger("ingestion.publisher")


class QueuePublisher:
    def __init__(self, host: str, port: int, user: str, password: str, queue: str):
        self._params = pika.ConnectionParameters(
            host=host, port=port, credentials=pika.PlainCredentials(user, password),
            heartbeat=30,
        )
        self._queue = queue
        self._connection = None
        self._channel = None

    def connect(self) -> None:
        """Open the connection, waiting until RabbitMQ is ready (it starts slowly)."""
        while True:
            try:
                self._connection = pika.BlockingConnection(self._params)
                self._channel = self._connection.channel()
                # durable: the queue itself survives a RabbitMQ restart
                self._channel.queue_declare(queue=self._queue, durable=True)
                log.info("connected to RabbitMQ, queue %s", self._queue)
                return
            except AMQPError as error:
                log.warning("RabbitMQ not ready (%s), retrying in 3 s", type(error).__name__)
                time.sleep(3)

    def publish(self, message: dict) -> None:
        """Send one JSON message; on a broken connection, reconnect and try once more."""
        body = json.dumps(message).encode()
        for attempt in (1, 2):
            try:
                self._channel.basic_publish(
                    exchange="",                       # default exchange: route by queue name
                    routing_key=self._queue,
                    body=body,
                    properties=pika.BasicProperties(
                        content_type="application/json",
                        delivery_mode=2,               # persistent: saved to disk
                    ),
                )
                return
            except (AMQPError, AttributeError):
                if attempt == 2:
                    raise
                log.warning("publish failed, reconnecting")
                self.connect()

    def close(self) -> None:
        if self._connection and self._connection.is_open:
            self._connection.close()
