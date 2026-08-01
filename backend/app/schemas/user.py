from pydantic import BaseModel, EmailStr


class UserCreateSchema(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserReadSchema(BaseModel):
    name: str
    email: EmailStr


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str
