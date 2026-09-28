from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float
    in_stock: bool = True

items = {}

@app.post("/items")
def create_item(item: Item):
    item_id = len(items) + 1
    items[item_id] = item

    return {
        "item_id": item_id,
        "item": item
    }

@app.get("/items/{item_id}")
def get_item(item_id: int):
    return {
        "item_id": item_id,
        "item": items.get(item_id)
    }

# @app.post("/items")
# def create_item(item: Item):
#     return {
#         "message": "Item created successfully",
#         "item": item
#     }

@app.get("/health")
def health_check():
    return {"status": "healthy"}


# @app.get("/items/{item_id}")
# def read_item(item_id: int):
#     return {"item_id": item_id}


@app.get("/items")
def list_items(limit: int = 5, category = str  | None):
    return {
        "limit": limit,
        "category": category
    }