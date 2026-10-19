from fastapi import FastAPI, Depends, HTTPExceptions 
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, JSON, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session, Mapped, mapped_column
from pydantic import BaseModel, EmailStr, Field, model_validator, field_validator
from enum import Enum
from datetime import datetime
from typing import Optional, List
import re


load_dotenv()
DATABASE_URL= os.getenv("DB_URL")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread" : False})
SessionLocal= sessionmaker(autoflush=False, autocommit=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] =  mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    discount_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list] = mapped_column(JSON)
    sku: Mapped[str] = mapped_column(String,  unique= True)
    stock_count: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[int] = mapped_column(Integer, default=0)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    dimensions: Mapped[dict] = mapped_column(JSON)
    features: Mapped[list] = mapped_column(JSON)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    address: Mapped[dict] = mapped_column(JSON)
    registered_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    preferences: Mapped[dict] = mapped_column(JSON)


Base.metadata.create_all(bind=engine)

# PYDANTIC VALIDATIONS
class Dimension(BaseModel):
    height: float = Field(gt=0)
    width: float = Field(gt=0)
    depth: float = Field(gt=0)

class Category(str, Enum):
    ELECTRONICS = "electronics"
    FASHION = "fashion"
    BEAUTY = "beauty"
    EDIBLES = "edibles"
    FURNITURES = "furnitures"
    UTENSILS = "utensils"
    BOOKS = "books"

class Feature(BaseModel):
    name: str
    description: str



class ProductBase(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    description: Optional[str] = Field(max_length=1000, default=None)
    price: float = Field(gt=0)
    discount_price: Optional[float] = None
    catgory: Category
    tags: List[str] = []
    sku: str
    stock_count: int = Field(ge=0)
    rating: float= Field(ge=0, le=5)
    is_available: bool = True
    dimensions: Dimension
    features: List[Feature] = []
    created_at: datetime = Field(default_factory=datetime.now)


    # Category Validator
    # @field_validator("category")
    # @classmethod
    # def validate_category(cls, value):
    #     for category in Category:
    #         if value != category:
    #             raise ValueError("Invalid Category")
    #     return value



    # Tags Validator
    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value):
        if len(value) > 10:
            raise ValueError("Maximum of 10 tags")
        for tag in value:
            if len(tag) < 2:
                raise ValueError("Tag is too short")
            if len(tag) > 15:
                raise ValueError("Tag is too long")
        return value

    # Sku Validator 
    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value):
        pattern = r"^[A-Z]{3}-\d{5}$"   #r"^\+?d[0-9]{11,15}"
        if not re.match (pattern, value):
            raise ValueError("SKU must follow ABC-12345")
        return value

 # Discount_price Validator
    @model_validator(mode="after") #(after validates model after its individual fields are validated)
    def validate_discount(self):
        if self.discount_price is not None:
            if self.discount_price >= self.price:
                raise ValueError("Discount must be less than price")
        return self


class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: str | None= Field(None, min_length=3, max_length=50)
    description: str | None= Field(None, max_length=1000)
    price: float | None = Field(None, gt=0)
    discount_price | None = Field(None, gt=0)
    category: Category | None = None
    tags: list[str] | None = Field(None, max_length=10)
    sku: str | None = None
    stock_count: int | None = Field(None, ge=0)
    rating: float | None = Field(None, ge=0, le=5)
    is_available: bool | None = None
    dimension: Dimension | None = None
    featuures: list[Feature] | None = None

 

app = FastAPI()


def get_db():
    db=SessionLocal()
    try:
        yield db
    except Exception as e:
        print (e)
        print ("Database Error")
        raise e
    finally:
        db.close()



# POST /products/: Add new product with validation
@app.post("/products")
def add_product(payload:ProductCreate, db:Session=Depends(get_db)):
    query= select(Product).where(Product.sku==payload.sku)
    existing_product= db.execute(query).scalar_one_or_none()
    if existing_product:
        raise HTTPExceptions(
            status_code=400,
            detail= "Sku already exists"
        )
    new_product= Product(
        name = payload.name,
        description = payload.description,
        price = payload.price,
        discount_price = payload.discount_price,
        category = payload.category.value,
        tags = payload.tags,
        sku = payload.sku,
        stock_count = payload.stock_count,
        rating = payload.rating,
        is_available = payload.is_available,
        created_at = payload.created_at, 
        dimension = payload.dimension.model_dump(),
        features = [feature.model_dump()
                   for feature in payload.features
        ]
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return {
        "status_code": 201,
        "message": "Product created successfully",
        "data": new_product
    }


@app.get("/products")
def get_products(
    db:Session=Depends(get_db),
    category: Optional[str]=None,
    min_price: Optional[float]=None,
    max_price: Optional[float]=None,
    is_available: Optional[bool]=None
    ):
    query = select(Product)
    if category:
        query = query.where(Product.category==category)
    if min_price:
        query = query.where(Product.price >= min_price)
    if max_price:
        query = query.where(Product.price <= max_price)
    if is_available:
        query = query.where(Product.is_available == is_available)
    products= db.execute(query).scalars().all()
    if not products:
        raise HTTPExceptions(
            status_code = 404,
            detail = "Product not found"
        ) 
    return {
        "status_code": 200,
        "message": "all products retrieved",
        "data": products
    }

# GET /products/{product_id}: Get product by ID
@app.get("/products/{product_id}", tags=["Product"])
def get_product_id(id:int, db:Session=Depends(get_db)):
    query = select(Product).where(Product.id==id)
    product = db.execute(query).scalar_one_or_none()
    if product is None:
        raise HTTPExceptions(
            status_code= 404,
            detail= "Product not found"
        )
    return {
        "status_code": 200,
        "message": "Product retrieved successfully",
        "data": product
    }

# PUT /products/{product_id}: Update product
@app.put("/products/{product_id}", tags=["Products"])
def update_product(payload:(args):
                   
    
