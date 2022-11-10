import json
import base64
import datetime

def lambda_handler(event, context):
    list_items = []
    
    for item in event['records']:
        parsed = json.loads(base64.b64decode(item['data']).decode("ascii"))
        
        if 'NewImage' not in parsed['dynamodb']:
            print(parsed['dynamodb'])
            continue
        
        empty,empty,country,empty,product_id = parsed['dynamodb']['NewImage']['sk']['S'].split("#")
    
        wishlist = None
        if "wishlist" in parsed['dynamodb']['NewImage']:
            wishlist = True
        
        data = {
            'evento_type': parsed['eventName'],
            'timestamp': datetime.datetime.fromtimestamp(parsed['dynamodb']['ApproximateCreationDateTime']/1000).strftime("%Y-%m-%d %H:%M:%S.%f"),
            'quantity': parsed['dynamodb']['NewImage']['quantity']['N'],
            'user_id': parsed['dynamodb']['NewImage']['pk']['S'],
            'country': country,
            'product_id': product_id,
            'wishlist': wishlist
        }
        
        output_record = {
            'recordId': item['recordId'],
            'result': 'Ok',
            'data': base64.b64encode(json.dumps(data).encode('utf-8')).decode('utf-8')
        }
        list_items.append(output_record)
    
    print(list_items)
    
    return {'records': list_items}