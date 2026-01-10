from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str
