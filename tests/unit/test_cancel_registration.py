import json
import os
import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def tables():
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
            AttributeDefinitions=[{'AttributeName': 'registrationId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )

        events_table.put_item(Item={'eventId': 'evt-test', 'capacity': 10, 'remaining': 3})
        registrations_table.put_item(Item={
            'registrationId': 'reg-1',
            'eventId': 'evt-test',
            'email': 'user@example.com',
            'timestamp': '2026-01-01T00:00:00'
        })

        yield {'events': events_table, 'registrations': registrations_table}


def test_cancel_registration_success(tables):
    from functions.cancel_registration.app import lambda_handler

    event = {'pathParameters': {'id': 'reg-1'}}
    response = lambda_handler(event, {})

    assert response['statusCode'] == 200

    # Registration should be gone
    remaining_reg = tables['registrations'].get_item(Key={'registrationId': 'reg-1'})
    assert 'Item' not in remaining_reg

    # Capacity should be given back: 3 -> 4
    updated_event = tables['events'].get_item(Key={'eventId': 'evt-test'})['Item']
    assert updated_event['remaining'] == 4


def test_cancel_registration_not_found(tables):
    from functions.cancel_registration.app import lambda_handler

    event = {'pathParameters': {'id': 'does-not-exist'}}
    response = lambda_handler(event, {})

    assert response['statusCode'] == 404


def test_cancel_registration_missing_id(tables):
    from functions.cancel_registration.app import lambda_handler

    event = {'pathParameters': {}}
    response = lambda_handler(event, {})

    assert response['statusCode'] == 400
