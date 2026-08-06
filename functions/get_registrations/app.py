import json
import boto3
import os
from decimal import Decimal
from urllib.parse import unquote

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['REGISTRATIONS_TABLE'])

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
        raw_email = event.get('pathParameters', {}).get('email')
        if not raw_email:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'email path parameter is required'})
            }

        # Path parameters can be URL-encoded (e.g. %40 for @), so decode it
        email = unquote(raw_email)

        response = table.query(
            IndexName='EmailIndex',
            KeyConditionExpression='email = :email',
            ExpressionAttributeValues={':email': email}
        )
        registrations = response.get('Items', [])

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(registrations, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error retrieving registrations: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Failed to retrieve registrations'})
        }