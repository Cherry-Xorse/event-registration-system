import json
import os
import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def events_table():
    """Spin up a fake in-memory DynamoDB table for testing, so we never touch real AWS."""
    with mock_aws():
        os.environ['EVENTS_TABLE'] = 'Events'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        table = dynamodb.create_table(
            TableName='Events',
            KeySchema=[{'AttributeName': 'eventId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'eventId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        table.put_item(Item={
            'eventId': 'evt-test',
            'eventName': 'Test Event',
            'eventDate': '2026-01-01',
            'capacity': 10,
            'remaining': 5
        })
        yield table


def test_list_events_returns_200_and_events(events_table):
    # Import inside the test so it picks up the mocked AWS environment set in the fixture
    from functions.list_events.app import lambda_handler

    response = lambda_handler({}, {})

    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert len(body) == 1
    assert body[0]['eventId'] == 'evt-test'
    assert body[0]['remaining'] == 5


def test_list_events_returns_empty_list_when_no_events():
    with mock_aws():
        os.environ['EVENTS_TABLE'] = 'Events'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

        dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        dynamodb.create_table(
            TableName='Events',
            KeySchema=[{'AttributeName': 'eventId', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'eventId', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )

        from functions.list_events.app import lambda_handler
        response = lambda_handler({}, {})

        assert response['statusCode'] == 200
        assert json.loads(response['body']) == []