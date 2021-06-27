import json
from os import path
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


# print(api.InAppProduct)


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
async def new_product(sku: str):
    try:
        api.delete(packageName=packageName, sku=sku).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    write_product(sku)


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
