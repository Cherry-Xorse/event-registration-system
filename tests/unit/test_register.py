import json
import os
import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def tables():
    """Spin up fake in-memory Events and Registrations tables for testing."""
    with mock_aws():
        os.environ['EVENTS_TABLE'] = 'Events'
        os.environ['REGISTRATIONS_TABLE'] = 'Registrations'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

        events_table = dynamodb.create_table(
            TableName='Events',
            KeySchema=[{'AttributeName': 'eventId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'eventId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        registrations_table = dynamodb.create_table(
            TableName='Registrations',
            KeySchema=[{'AttributeName': 'registrationId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[
                {'AttributeName': 'registrationId', 'AttributeType': 'S'},
                {'AttributeName': 'email', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[{
                'IndexName': 'EmailIndex',
                'KeySchema': [{'AttributeName': 'email', 'KeyType': 'HASH'}],
                'Projection': {'ProjectionType': 'ALL'}
            }],
            BillingMode='PAY_PER_REQUEST'
        )

        events_table.put_item(Item={
            'eventId': 'evt-test',
            'eventName': 'Test Event',
            'capacity': 10,
            'remaining': 1  # only 1 spot left, so we can test the sold-out path easily
        })

        yield {'events': events_table, 'registrations': registrations_table}


def test_register_success(tables):
    from functions.register.app import lambda_handler

    event = {'body': json.dumps({'eventId': 'evt-test', 'email': 'user@example.com'})}
    response = lambda_handler(event, {})

    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    assert 'registrationId' in body

    # Confirm remaining capacity actually decremented
    updated = tables['events'].get_item(Key={'eventId': 'evt-test'})['Item']
    assert updated['remaining'] == 0


def test_register_missing_fields(tables):
    from functions.register.app import lambda_handler

    event = {'body': json.dumps({'eventId': 'evt-test'})}  # no email
    response = lambda_handler(event, {})

    assert response['statusCode'] == 400


def test_register_invalid_email(tables):
    from functions.register.app import lambda_handler

    event = {'body': json.dumps({'eventId': 'evt-test', 'email': 'not-an-email'})}
    response = lambda_handler(event, {})

    assert response['statusCode'] == 400


def test_register_fails_when_sold_out(tables):
    from functions.register.app import lambda_handler

    # Use up the last spot
    first = lambda_handler({'body': json.dumps({'eventId': 'evt-test', 'email': 'a@example.com'})}, {})
    assert first['statusCode'] == 201

    # This one should be rejected — no capacity left
    second = lambda_handler({'body': json.dumps({'eventId': 'evt-test', 'email': 'b@example.com'})}, {})
    assert second['statusCode'] == 409