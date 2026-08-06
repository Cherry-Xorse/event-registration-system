import json
import os
import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def registrations_table():
    with mock_aws():
        os.environ['REGISTRATIONS_TABLE'] = 'Registrations'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
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
        table.put_item(Item={
            'registrationId': 'reg-1',
            'eventId': 'evt-test',
            'email': 'user@example.com',
            'timestamp': '2026-01-01T00:00:00'
        })
        yield table


def test_get_registrations_returns_matches(registrations_table):
    from functions.get_registrations.app import lambda_handler

    event = {'pathParameters': {'email': 'user@example.com'}}
    response = lambda_handler(event, {})

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body) == 1
    assert body[0]['registrationId'] == 'reg-1'


def test_get_registrations_returns_empty_for_unknown_email(registrations_table):
    from functions.get_registrations.app import lambda_handler

    event = {'pathParameters': {'email': 'nobody@example.com'}}
    response = lambda_handler(event, {})

    assert response['statusCode'] == 200
    assert json.loads(response['body']) == []


def test_get_registrations_missing_email_param(registrations_table):
    from functions.get_registrations.app import lambda_handler

    event = {'pathParameters': {}}
    response = lambda_handler(event, {})

    assert response['statusCode'] == 400
