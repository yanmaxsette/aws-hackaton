import sys
import boto3
import urllib3
from boto3.dynamodb.conditions import Key, Attr
import json
from chalice import Chalice
from urllib.parse import urlparse, parse_qs

#
# curl -d '{"user_id":"3","country":"usa","product_id":"3","quantity":"1000"}' -H "Content-Type: application/json" -X POST https://5wnfasax8l.execute-api.us-west-2.amazonaws.com/api/add
# curl -d '{"user_id":"3","country":"usa","product_id":"200"}' -H "Content-Type: application/json" -X DELETE https://5wnfasax8l.execute-api.us-west-2.amazonaws.com/api/delete
# curl -d '{"user_id":"1","country":"usa"}' -H "Content-Type: application/json" -X POST https://5wnfasax8l.execute-api.us-west-2.amazonaws.com/api/search
# curl -d '{"user_id":"1","country":"brazil"}' -H "Content-Type: application/json" -X DELETE https://5wnfasax8l.execute-api.us-west-2.amazonaws.com/api/clear
#

app = Chalice(app_name='cart')

client = boto3.client('dynamodb')

@app.route('/')
def index():
    return {'hello': 'world'}


@app.route('/add', methods=['POST'], cors=True)
def add():
    parsed = app.current_request.json_body
    
    country = parsed['country']
    if country is None:
      country = "usa"
    
    pk = "#user_id#" + parsed['user_id']
    sk = "#country#" + country + "#product_id#" + parsed['product_id']
    quantity = parsed['quantity']
    
    product = find_product(parsed['product_id'])
    
    if (product['quantity'] < float(quantity)):
      return {
            'statusCode': 200,
            'body': {
              'message' : 'There\'s no quantity available!',
              'status' : 500
            },
            'headers': {
              'Content-Type': 'application/json',
              'Access-Control-Allow-Origin': '*'
            },
      }
    
    data = client.put_item(
        TableName='cart',
        Item=
          {
            "pk": {"S": pk},
            "sk": {"S":  sk},
            "quantity": {"N": quantity}
          }
    )

    response = {
          'statusCode': 200,
          'body': {
              'message' : 'successfully created item!',
              'status' : 200
          },
          'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
          },
    }
  
    return response
    
    
@app.route('/importwishlist', methods=['POST'], cors=True)
def importwishlist():
  parsed = app.current_request.json_body
  user_id = parsed['user_id']
  wishlist_id = parsed['wishlist_id']
  
  wishlist = get_wishlist(user_id, wishlist_id)
  
  response = []
  
  for item in wishlist['body']:
      country = "usa"
    
      pk = "#user_id#" + user_id
      sk = "#country#" + country + "#product_id#" + str(int(item['productID']))
      quantity = str(item['quantity'])
    
      product = find_product(item['productID'])
      
      if product is None:
        response.append({
          'item' : item['productID'],
          'status': 500,
          'message': "Product not found"
        })
      elif (product['quantity'] < float(quantity)):
        response.append({
          'item' : item['productID'],
          'status': 500,
          'message': "Quantity not available"
        })
      else:
        data = client.put_item(
            TableName='cart',
            Item=
              {
                "pk": {"S": pk},
                "sk": {"S":  sk},
                "quantity": {"N": quantity},
                "wishlist": {"BOOL": True}
              }
        )
        response.append({
          'item' : item['productID'],
          'status': 200,
          'message': "Successful created!"
        })
      
  return response
  
    
@app.route('/delete', methods=['DELETE'], cors=True)
def delete():
    parsed = app.current_request.json_body
    
    pk = "#user_id#" + parsed['user_id']
    sk = "#country#" + parsed['country'] + "#product_id#" + parsed['product_id']
    
    data = client.delete_item(
        TableName='cart',
        Key=
          {
            "pk": {"S": pk},
            "sk": {"S":  sk}
          }
    )

    response = {
          'statusCode': 200,
          'body': 'successfully deleted item!',
          'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
          },
    }
  
    return response
    

@app.route('/search', methods=['POST'], cors=True)
def search():
    parsed = app.current_request.json_body
    pk = "#user_id#" + parsed['user_id']
    sk = "#country#" + parsed['country']
    
    coupon_used = None
    if 'coupon' in parsed:
      coupon_used = parsed['coupon']
    zip_code = None
    if 'zip_code' in parsed:
      zip_code = parsed['zip_code']
      
    data = client.query(
        TableName='cart',
        KeyConditionExpression='pk = :pk AND begins_with ( sk , :sk )',
        ExpressionAttributeValues={
            ':pk': {'S': pk},
            ':sk': {'S': sk}
        }   
    )
    
    total_cart_price = 0
    total_quantity = 0
    list_items = []

    for i in data['Items']:
      empty,empty,country,empty,product_id = i['sk']['S'].split("#")
      quantity = int(i['quantity']['N'])
      product = find_product(product_id)
      list_items.append({
        'user_id' : i['pk']['S'].split("#")[2],
        'product_id' : product_id,
        'quantity' : quantity,
        'price' : product['price'],
        'total_price_item': quantity * product['price']
      })
      total_cart_price += quantity * product['price']
      total_quantity += quantity
    
    total_with_discount = coupon(coupon_used, total_cart_price)
    
    shipping_cost = calc_shipping(zip_code, total_quantity)
    
    response = {
          'statusCode': 200,
          'items': list_items,
          'total_quantity': total_quantity,
          'coupon_discount': coupon_used,
          'total_price': total_cart_price,
          'total_price_with_discount': total_with_discount,
          'shipping_cost': shipping_cost,
          'final_total': total_with_discount + shipping_cost,
          'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
          },
    }
    
    return response
    
    
    
def find_product(product_id):
    url = 'https://40q5712bx5.execute-api.us-west-2.amazonaws.com/api/getproducts'

    payload = json.dumps({
        "category": "clothes",
        "productID": product_id
    })
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    http = urllib3.PoolManager()
    encoded_payload = payload.encode("utf-8")

    try:
      request = http.request("POST", url=url, headers=headers, body=encoded_payload)
    except:
      print("An exception occured during API Call")
    
    request_data = json.loads(request.data.decode("utf-8"))
    
    return request_data
  
  
  
def get_wishlist(user_id, wishlist_id):
    url = ('https://tj1u4jy050.execute-api.us-west-2.amazonaws.com/api/getwishlist?userid={}&wishlistid={}').format(user_id, wishlist_id)
    
    http = urllib3.PoolManager()

    try:
      request = http.request("GET", url=url)
    except:
      print("An exception occured during API Call")
    
    request_data = json.loads(request.data.decode("utf-8"))
    
    print(request_data)
    
    return request_data
  
  
@app.route('/clear', methods=['DELETE'], cors=True)
def clear():
    parsed = app.current_request.json_body
    
    pk = "#user_id#" + parsed['user_id']
    sk = "#country#" + parsed['country']
    
    data = client.query(
        TableName='cart',
        KeyConditionExpression='pk = :pk AND begins_with ( sk , :sk )',
        ExpressionAttributeValues={
            ':pk': {'S': pk},
            ':sk': {'S': sk}
        }   
    )
    
    for item in data['Items']:
        client.delete_item(
            TableName='cart',
            Key=
              {
                "pk": {"S": item['pk']['S']},
                "sk": {"S":  item['sk']['S']}
              }
        )


    response = {
          'statusCode': 200,
          'body': 'successfully deleted items!',
          'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
          },
    }
  
    return response
    
    
def coupon(code, total_price):
  list_coupons = {
    '50OFF' : 50,
    '25OFF' : 25,
    '10OFF' : 10,
    'kart_is_the_best': 100
  }
  
  if code in list_coupons:
    total_price = total_price - (total_price * (list_coupons[code] / 100))
    
  return total_price
  

def calc_shipping(zip_code, number_of_products):
  
  if zip_code is None:
    return 0
    
  first_number = int(zip_code[0])
  
  prices = {
    0: 10,
    1: 10,
    2: 8,
    3: 4,
    4: 7,
    5: 7,
    6: 4,
    7: 2,
    8: 5,
    9: 7
  }
  
  return prices[first_number] + (prices[first_number] * number_of_products / 100)
  
# The view function above will return {"hello": "world"}
# whenever you make an HTTP GET request to '/'.
#
# Here are a few more examples:
#
# @app.route('/hello/{name}')
# def hello_name(name):
#    # '/hello/james' -> {"hello": "james"}
#    return {'hello': name}
#
# @app.route('/users', methods=['POST'])
# def create_user():
#     # This is the JSON body the user sent in their POST request.
#     user_as_json = app.current_request.json_body
#     # We'll echo the json body back to the user in a 'user' key.
#     return {'user': user_as_json}
#
# See the README documentation for more examples.
#
