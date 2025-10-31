import logging
from google.cloud import pubsub_v1
from aegnix_ae.transport.transport_base import BaseTransport

log = logging.getLogger(__name__)

class GcpPubSubAdapter(BaseTransport):
    def __init__(self, project_id="aegnix-dev", mock=False):
        self.project_id = project_id
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()

    def publish(self, subject, message):
        topic_path = self.publisher.topic_path(self.project_id, subject)
        self.publisher.publish(topic_path, message.encode("utf-8"))
        log.debug(f"Published to {topic_path}")

    def subscribe(self, subject, handler):
        subscription_path = self.subscriber.subscription_path(self.project_id, f"{subject}-sub")
        def callback(msg):
            log.debug(f"Received message on {subject}")
            handler(msg.data)
            msg.ack()
        self.subscriber.subscribe(subscription_path, callback=callback)
