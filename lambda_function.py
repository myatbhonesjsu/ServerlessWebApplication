import json
import os
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key  # noqa

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'StudentRecords')
table = dynamodb.Table(TABLE_NAME)

def _response(status, body):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json',
            # Basic CORS; tighten to your domain in production
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,GET,POST,PUT,DELETE'
        },
        'body': json.dumps(body)
    }

def lambda_handler(event, context):
    method = event.get('httpMethod', '')
    path_params = event.get('pathParameters') or {}
    qs = event.get('queryStringParameters') or {}
    student_id = path_params.get('student_id') or qs.get('student_id')

    try:
        # Handle CORS preflight when using REST API with proxy integration
        if method == 'OPTIONS':
            return _response(200, {'ok': True})

        if method == 'POST':
            # Create: body must include a unique student_id
            item = json.loads(event.get('body') or '{}')
            if 'student_id' not in item:
                return _response(400, {'error': 'student_id is required'})
            table.put_item(
                Item=item,
                ConditionExpression='attribute_not_exists(student_id)'
            )
            return _response(201, {'message': 'Student created', 'student_id': item['student_id']})

        if method == 'GET':
            # Read by ID (supports either /students?student_id=... or /students/{student_id})
            if not student_id:
                return _response(400, {'error': 'student_id is required'})
            resp = table.get_item(Key={'student_id': student_id})
            if 'Item' not in resp:
                return _response(404, {'error': 'Not found'})
            return _response(200, resp['Item'])

        if method == 'PUT':
            # Update by ID (fields in body except student_id)
            if not student_id:
                return _response(400, {'error': 'student_id is required'})
            payload = json.loads(event.get('body') or '{}')
            update_expr = []
            expr_attr_vals = {}
            expr_attr_names = {}
            for k, v in payload.items():
                if k == 'student_id':
                    continue
                update_expr.append(f"#_{k} = :{k}")
                expr_attr_vals[f":{k}"] = v
                expr_attr_names[f"#_{k}"] = k
            if not update_expr:
                return _response(400, {'error': 'No fields to update'})
            res = table.update_item(
                Key={'student_id': student_id},
                UpdateExpression='SET ' + ', '.join(update_expr),
                ExpressionAttributeValues=expr_attr_vals,
                ExpressionAttributeNames=expr_attr_names,
                ConditionExpression='attribute_exists(student_id)',
                ReturnValues='ALL_NEW'
            )
            return _response(200, res['Attributes'])

        if method == 'DELETE':
            # Delete by ID
            if not student_id:
                return _response(400, {'error': 'student_id is required'})
            table.delete_item(
                Key={'student_id': student_id},
                ConditionExpression='attribute_exists(student_id)'
            )
            # 204 = No Content; body may be empty
            return _response(204, {})

    except ClientError as e:
        code = e.response['Error']['Code']
        if code == 'ConditionalCheckFailedException':
            return _response(409, {'error': 'Conflict or not found'})
        return _response(500, {'error': e.response['Error']['Message']})
    except Exception as e:
        return _response(500, {'error': str(e)})

    return _response(405, {'error': f'Method {method} not allowed'})
