import json
import boto3
import os
import uuid
from datetime import datetime
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
events_table = dynamodb.Table(os.environ['EVENTS_TABLE'])
registrations_table = dynamodb.Table(os.environ['REGISTRATIONS_TABLE'])

def lambda_handler(event, context):
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }

    try:
        body = json.loads(event.get('body') or '{}')
        event_id = body.get('eventId')
        email = body.get('email')

        # Input validation
        if not event_id or not email:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'eventId and email are required'})
            }
        if '@' not in email or '.' not in email:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid email format'})
            }

        # Atomically decrement remaining capacity, but only if remaining > 0
        try:
            events_table.update_item(
                Key={'eventId': event_id},
                UpdateExpression='SET remaining = remaining - :dec',
                ConditionExpression='remaining > :zero',
                ExpressionAttributeValues={':dec': 1, ':zero': 0}
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return {
                    'statusCode': 409,
                    'headers': headers,
                    'body': json.dumps({'error': 'Event is full or does not exist'})
                }
            raise

        # Create the registration record
        registration_id = str(uuid.uuid4())
        registrations_table.put_item(Item={
            'registrationId': registration_id,
            'eventId': event_id,
            'email': email,
            'timestamp': datetime.utcnow().isoformat()
        })

        return {
            'statusCode': 201,
            'headers': headers,
            'body': json.dumps({
                'registrationId': registration_id,
                'message': 'Registration successful'
            })
        }

    except Exception as e:
        print(f"Error registering: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to process registration'})
        }