"""Read messages from RabbitMQ and hand each one to a function."""
import json
import logging
import time

import pika
from pika.exceptions import AMQPError

log = logging.getLogger("ingestion.queue")


class QueueConsumer:
    def __init__(self, host: str, port: int, user: str, password: str, queue: str):
        self._params = pika.ConnectionParameters(
            host=host, port=port, credentials=pika.PlainCredentials(user, password),
            heartbeat=30,
        )
        self._queue = queue

    def consume(self, handler, should_run) -> None:
        """Call handler(message_dict) for each message until should_run() is False.

        A message is acknowledged (removed from the queue) only after the handler
        succeeded, so a crash in the middle means it is delivered again, never lost.
        """
        while should_run():
            try:
                connection = pika.BlockingConnection(self._params)
                channel = connection.channel()
                channel.queue_declare(queue=self._queue, durable=True)
                channel.basic_qos(prefetch_count=1)   # one unacknowledged message at a time
                log.info("connected to RabbitMQ, waiting for messages on %s", self._queue)

                # wake up every second to check should_run(), even when the queue is empty
                for method, _props, body in channel.consume(self._queue, inactivity_timeout=1):
                    if not should_run():
                        break
                    if method is None:
                        continue  # timeout, no message
                    try:
                        handler(json.loads(body))
                    except (ValueError, KeyError, TypeError):
                        log.exception("bad message dropped: %r", body[:200])
                        channel.basic_nack(method.delivery_tag, requeue=False)
                        continue
                    channel.basic_ack(method.delivery_tag)
                connection.close()
            except AMQPError as error:
                log.warning("RabbitMQ problem (%s), retrying in 3 s", type(error).__name__)
                time.sleep(3)
