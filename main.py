import os
import json
import requests
from os import path
import firebase_admin
from datetime import datetime
from firebase_admin import credentials
from firebase_admin import firestore
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from googleapiclient import discovery
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2.service_account import Credentials

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*", "POST"],
    allow_headers=["*"],
)

cred = credentials.Certificate('firestore.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

credentials = Credentials.from_service_account_file(
    'credentials.json',
    scopes=['https://www.googleapis.com/auth/androidpublisher']
)
api = discovery.build('androidpublisher', 'v3', credentials=credentials).inappproducts()

data = {}

# Read Configurations in start
if not path.exists('data'):
    with open('data', 'w') as _:
        _.write('{}')

with open('data') as file:
    data = json.loads(file.read())

packageName = 'com.kingofthecurve.kingofthecurve'

class IAPProduct(BaseModel):
    id: str
    name: str
    type: str
    price: float
    discount: float
    description: str
    discountMode: bool
    subscriptionPeriod: str


@app.get('/get-products')
async def get_all_products_google():
    products = api.list(packageName=packageName).execute()
    for product in products['inappproduct']:
        if product['sku'] in data:
            detail = data[product['sku']]
            discountMode = detail['discountMode']

            product['discount'] = detail['discount']
            if discountMode:
                product['defaultPrice']['priceMicros'] = detail['price'] * 1000000
            product['discountMode'] = detail['discountMode']
    return products


@app.post('/update-product')
async def update_product(product: IAPProduct):
    try:
        api.update(packageName=packageName, sku=product.id, autoConvertMissingPrices=True, body={
            'sku': product.id,
            'status': 'active',
            'packageName': packageName,
            'purchaseType': product.type,
            'defaultPrice': {
                'priceMicros': str(int((product.discount if product.discountMode else product.price) * 1000000)),
                'currency': 'USD'
            },
            'listings': {
                'en-US': {
                    'title': product.name,
                    'description': product.description,
                }
            },
            'subscriptionPeriod': product.subscriptionPeriod
        }).execute()
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    write_product(product)


@app.post('/new-product')
async def new_product(product: IAPProduct):
    try:
        api.insert(packageName=packageName, autoConvertMissingPrices=True, body={
            'sku': product.id,
            'status': 'active',
            'packageName': packageName,
            'purchaseType': product.type,
            'defaultPrice': {
                'priceMicros': str(int(product.price * 1000000)),
                'currency': 'USD'
            },
            'listings': {
                'en-US': {
                    'title': product.name,
                    'description': product.description,
                }
            }
        }).execute()
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
    write_product(product)


@app.delete('/delete-product/{sku}')
async def delete_product(sku: str):
    try:
        api.delete(packageName=packageName, sku=sku).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    write_product(sku)

@app.get('/update-institutions')
async def update_institutions_from_source():
    new_data = json.loads(requests.get('https://raw.githubusercontent.com/Hipo/university-domains-list/master/world_universities_and_domains.json').content)
    filtered_data = []

    for item in new_data:
        code = item['alpha_two_code']
        if code == 'US' or code == 'CA':
            filtered_data.append(item)

    if os.path.exists('institutes.json'):
        data = []
        with open('institutes.json') as file:
            data = json.loads(file.read())

        for item in filtered_data:
            for item2 in data:
                if item['name'] == item2['name']:
                    new_domains = []
                    new_web_pages = []

                    for domain in item['domains']:
                        if domain not in new_domains:
                            new_domains.append(domain)

                    for web_page in item['web_pages']:
                        if web_page not in new_web_pages:
                            new_web_pages.append(web_page)

                    for domain in item2['domains']:
                        if domain not in new_domains:
                            new_domains.append(domain)

                    for web_page in item2['web_pages']:
                        if web_page not in new_web_pages:
                            new_web_pages.append(web_page)
                
                    item2['domains'] = new_domains
                    item2['web_pages'] = new_web_pages
 
        with open('institutes.json', 'w') as result:
            result.write(json.dumps(data))
    else:
        with open('institutes.json', 'w') as result:
            result.write(json.dumps(filtered_data))


@app.get('/institutions')
async def get_all_institutions():
    return ['1', '2', '3', '4', '5']

@app.get('/find-institute/{domain}')
async def find_institute(domain: str):
    data = []

    if os.path.exists('institutes.json'):
        with open('institutes.json') as result:
            data = json.loads(result.read())

    for item in data:
        if domain in item['domains']:
            return item
    else:
        return {}

@app.get('/link-institute-email/{domain}/{id}')
async def link_institute_email(domain: str, id: str):
    user = db.collection('v2_users').document(id)
    user_data = user.get()
    if user_data.exists:
        user.update({
            'is_institution_verification_pending': True
        })



    # db.collection('v2_institution_verifications').add({
    #     'user': id,
    #     'started_at': datetime.now()
    # })
    # # .set({
    # #     'is_institution_verification_pending': True
    # # })
    # print(user)
    return {}


def write_product(product):
    if type(product) == 'str':
        if product in data:
            del data[product]
        return

    if product.id not in data or data[product.id] is None:
        data[product.id] = {}

    data[product.id] = {'price': product.price, 'discount': product.discount, 'discountMode': product.discountMode}
    with open('data', 'w') as output_file:
        output_file.write(json.dumps(data))
