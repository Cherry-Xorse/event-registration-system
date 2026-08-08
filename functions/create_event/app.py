import json
import boto3
import os
import uuid
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
events_table = dynamodb.Table(os.environ['EVENTS_TABLE'])


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def lambda_handler(event, context):
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }

    try:
        body = json.loads(event.get('body') or '{}')
        event_name = body.get('eventName')
        event_date = body.get('eventDate')
        capacity = body.get('capacity')

        # Input validation
        if not event_name or not event_date or capacity is None:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'eventName, eventDate, and capacity are required'})
            }

        try:
            capacity = int(capacity)
        except (ValueError, TypeError):
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'capacity must be a whole number'})
            }

        if capacity <= 0:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'capacity must be greater than 0'})
            }

        event_id = f"evt-{uuid.uuid4().hex[:8]}"

        item = {
            'eventId': event_id,
            'eventName': event_name,
            'eventDate': event_date,
            'capacity': capacity,
            'remaining': capacity,  # a brand-new event starts fully open
        }

        events_table.put_item(Item=item)

        return {
            'statusCode': 201,
            'headers': headers,
            'body': json.dumps(item, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error creating event: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to create event'})
        }