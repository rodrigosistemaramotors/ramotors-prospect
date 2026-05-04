from pydantic import BaseModel, EmailStr

class LoginInput(BaseModel):
    email: EmailStr
    senha: str

class TokenOutput(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshInput(BaseModel):
    refresh_token: str
