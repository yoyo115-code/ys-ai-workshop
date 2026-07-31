from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    invite_code: str = ""


class DeleteAccountRequest(BaseModel):
    password: str
