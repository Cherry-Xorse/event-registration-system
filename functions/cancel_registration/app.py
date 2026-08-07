import json
import boto3
import os

dynamodb = boto3.resource('dynamodb')
registrations_table = dynamodb.Table(os.environ['REGISTRATIONS_TABLE'])
events_table = dynamodb.Table(os.environ['EVENTS_TABLE'])

def lambda_handler(event, context):
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }

    try:
        registration_id = event.get('pathParameters', {}).get('id')
        if not registration_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'registration id is required'})
            }

        # First, fetch the registration so we know which event to credit back
        existing = registrations_table.get_item(Key={'registrationId': registration_id})
        item = existing.get('Item')

        if not item:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'Registration not found'})
            }

        event_id = item['eventId']

        # Delete the registration
        registrations_table.delete_item(Key={'registrationId': registration_id})

        # Give the spot back
        events_table.update_item(
            Key={'eventId': event_id},
            UpdateExpression='SET remaining = remaining + :inc',
            ExpressionAttributeValues={':inc': 1}
        )

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'Registration cancelled successfully'})
        }

    except Exception as e:
        print(f"Error cancelling registration: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to cancel registration'})
        }