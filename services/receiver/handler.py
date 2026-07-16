import boto3
import json
import os
import time
import uuid

sqs       = boto3.client('sqs', region_name='ap-south-1')
QUEUE_URL = os.environ.get('SQS_QUEUE_URL')


def handler(event, context):
    try:
        # Parse the incoming event body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        # Add server-side timestamp and event ID if not present
        body.setdefault('timestamp', time.time())
        body.setdefault('event_id', str(uuid.uuid4()))

        # Validate required fields
        if 'sensor_id' not in body:
            return response(400, {'error': 'sensor_id is required'})
        if 'value' not in body:
            return response(400, {'error': 'value is required'})

        # Send to SQS
        sqs.send_message(
            QueueUrl    = QUEUE_URL,
            MessageBody = json.dumps(body)
        )

        return response(200, {
            'status':   'accepted',
            'event_id': body['event_id']
        })

    except Exception as e:
        print(f"Error: {e}")
        return response(500, {'error': str(e)})


def handler_batch(event, context):
    """Accept a batch of events in one API call."""
    try:
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})

        events = body.get('events', [])
        if not events:
            return response(400, {'error': 'events array is required'})

        if len(events) > 10:
            return response(400, {'error': 'Maximum 10 events per batch'})

        # Send all events to SQS in one batch call
        entries = []
        for i, evt in enumerate(events):
            evt.setdefault('timestamp', time.time())
            evt.setdefault('event_id', str(uuid.uuid4()))
            entries.append({
                'Id':          str(i),
                'MessageBody': json.dumps(evt)
            })

        sqs.send_message_batch(
            QueueUrl = QUEUE_URL,
            Entries  = entries
        )

        return response(200, {
            'status':  'accepted',
            'count':   len(events)
        })

    except Exception as e:
        print(f"Batch error: {e}")
        return response(500, {'error': str(e)})


# ── Query Lambda — serves analytics data to dashboard ─────────────────────────
def handler_query(event, context):
    dynamodb   = boto3.resource('dynamodb', region_name='ap-south-1')
    TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
    table      = dynamodb.Table(TABLE_NAME)

    from boto3.dynamodb.conditions import Key

    params     = event.get('queryStringParameters') or {}
    sensor_id  = params.get('sensor_id', '')
    limit      = int(params.get('limit', '20'))

    try:
        if sensor_id:
            # Query specific sensor's recent windows
            result = table.query(
                KeyConditionExpression = Key('PK').eq(f'SENSOR#{sensor_id}'),
                ScanIndexForward       = False,
                Limit                  = limit
            )
        else:
            # Scan all sensors — for dashboard overview
            result = table.scan(Limit=50)

        items = result.get('Items', [])

        # Convert Decimal to float for JSON serialization
        import decimal
        def decimal_default(obj):
            if isinstance(obj, decimal.Decimal):
                return float(obj)
            raise TypeError

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type':                'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'count': len(items),
                'items': items
            }, default=decimal_default)
        }

    except Exception as e:
        return response(500, {'error': str(e)})


def response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type':                'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(body)
    }