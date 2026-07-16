import boto3
import json
import os
import time
import logging
from datetime import datetime, timezone
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients
sqs      = boto3.client('sqs', region_name='ap-south-1')
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')

QUEUE_URL      = os.environ.get('SQS_QUEUE_URL')
TABLE_NAME     = os.environ.get('DYNAMODB_TABLE')
table          = dynamodb.Table(TABLE_NAME)
WINDOW_SECONDS = 30


def process_batch(messages):
    """Aggregate a batch of events into 30-second windows."""
    aggregations = defaultdict(lambda: {
        'count':     0,
        'total':     0.0,
        'min_val':   float('inf'),
        'max_val':   float('-inf'),
        'event_types': defaultdict(int)
    })

    for msg in messages:
        try:
            body       = json.loads(msg['Body'])
            event_type = body.get('event_type', 'unknown')
            value      = float(body.get('value', 0))
            sensor_id  = body.get('sensor_id', 'unknown')

            # Time window key — round to nearest 30 seconds
            ts          = body.get('timestamp', time.time())
            window_ts   = int(ts // WINDOW_SECONDS) * WINDOW_SECONDS
            window_key  = f"{sensor_id}#{window_ts}"

            agg = aggregations[window_key]
            agg['count']              += 1
            agg['total']              += value
            agg['min_val']             = min(agg['min_val'], value)
            agg['max_val']             = max(agg['max_val'], value)
            agg['event_types'][event_type] += 1
            agg['sensor_id']           = sensor_id
            agg['window_ts']           = window_ts

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    return aggregations


def write_aggregations(aggregations):
    """Write aggregated windows to DynamoDB."""
    for window_key, agg in aggregations.items():
        sensor_id  = agg.get('sensor_id', 'unknown')
        window_ts  = agg.get('window_ts', int(time.time()))
        count      = agg['count']
        avg_val    = round(agg['total'] / count, 4) if count > 0 else 0

        # TTL — keep data for 24 hours only
        expires_at = window_ts + 86400

        table.put_item(Item={
            'PK':          f'SENSOR#{sensor_id}',
            'SK':          f'WINDOW#{window_ts}',
            'sensor_id':   sensor_id,
            'window_ts':   window_ts,
            'window_start': datetime.fromtimestamp(
                               window_ts, tz=timezone.utc).isoformat(),
            'count':       count,
            'avg_value':   str(avg_val),
            'min_value':   str(round(agg['min_val'], 4)),
            'max_value':   str(round(agg['max_val'], 4)),
            'event_types': json.dumps(dict(agg['event_types'])),
            'expires_at':  expires_at
        })

        logger.info(
            f"Written: sensor={sensor_id} window={window_ts} "
            f"count={count} avg={avg_val}"
        )


def delete_messages(messages):
    """Delete processed messages from SQS."""
    for msg in messages:
        sqs.delete_message(
            QueueUrl=QUEUE_URL,
            ReceiptHandle=msg['ReceiptHandle']
        )


def main():
    logger.info(f"Processor started. Queue: {QUEUE_URL}, Table: {TABLE_NAME}")

    while True:
        try:
            # Long poll SQS — waits up to 20 seconds for messages
            response = sqs.receive_message(
                QueueUrl            = QUEUE_URL,
                MaxNumberOfMessages = 10,
                WaitTimeSeconds     = 20,
                AttributeNames      = ['All']
            )

            messages = response.get('Messages', [])

            if not messages:
                logger.info("No messages — waiting...")
                continue

            logger.info(f"Received {len(messages)} messages")

            aggregations = process_batch(messages)
            write_aggregations(aggregations)
            delete_messages(messages)

            logger.info(f"Processed batch of {len(messages)} messages")

        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(5)


if __name__ == '__main__':
    main()