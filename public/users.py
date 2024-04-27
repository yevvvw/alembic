# Нужные библиотеки
from fastapi import APIRouter, Body, HTTPException, Depends
from models.dbcontext import *
from models.models_user import *
from typing import Annotated, Union
from fastapi.responses import JSONResponse
from public.db import get_session
from starlette import status
from sqlalchemy import select, insert, text, update

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os

from sqlalchemy.ext.asyncio import AsyncSession

# Хэширование данных пользователей
secretKey = b'vOVH6sdmpNWjRRIqCc7rdxs01lwHzfr3'

def coder_passwd(cod: str):
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(secretKey), modes.CFB(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(cod.encode()) + encryptor.finalize()
    return ciphertext.hex()

def decoder_passwd(hash):
    iv = bytes.fromhex(hash["iv"])
    content = bytes.fromhex(hash["content"])
    cipher = Cipher(algorithms.AES(secretKey), modes.CFB(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return (decryptor.update(content) + decryptor.finalize()).decode('utf-8')

U_R = APIRouter(tags = [Tags.users], prefix = '/api/users')

# Получения списка пользователей
@U_R.get("/", response_model = Union[list[Secondary_User], New_Respons], tags=[Tags.users])
async def get_users(database: AsyncSession = Depends(get_session)):
    users = await database.execute(select(User).order_by(User.id.asc()))
    users = users.scalars().all()
    if users == []:
        return JSONResponse(status_code=404, content={"message": "Таблица пользователей пуста"})
    return users
# Получение данных пользователя по его id
@U_R.get("/{id}", response_model = Union[Secondary_User, New_Respons], tags=[Tags.users])
async def get_user(id: int, database: AsyncSession = Depends(get_session)):
    try:
        user = await database.execute(select(User).where(User.id == id))
        return user.scalars().one()
    except Exception as e:
        return JSONResponse(status_code=404, content={"message": "Пользователь не найден"})
# Изменение данных пользователя
@U_R.put("/{id}", response_model = Union[Main_User, New_Respons], tags=[Tags.users])
async def edit_person(id: int, item: Annotated[Main_User, Body(embed = True, description = "Изменяем данные пользователя через его id")],
                      database: AsyncSession = Depends(get_session)):
    try:
        user = await database.execute(select(User).where(User.id == id))
        user = user.scalars().one()
    except Exception as e:
        return JSONResponse(status_code=404, content={"message": "Пользователь не найден"})
    try:
        user.name = item.name
        user.surname = item.surname
        await database.execute(text(f"update users set name=\'{user.name}\', surname=\'{user.surname}\' where id={id};"))
        await database.execute(text("commit;"))
        user = await database.execute(select(User).where(User.id == id))
        user = user.scalars().one()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Произошла ошибка в изменении объекта {user}")
    return user
# Добавление нового пользователя
@U_R.post("/", response_model = Union[Secondary_User, New_Respons], tags=[Tags.users], status_code=status.HTTP_201_CREATED)
async def create_user(item: Annotated[Main_User, Body(embed = True, description = "Новый пользователь")],
                      database: AsyncSession = Depends(get_session)):
    try:
        user = User(name = item.name, surname = item.surname, hashed_password = coder_passwd(item.surname))
        if user is None:
            raise HTTPException(status_code=404, detail="Объект не определён")
        await database.execute(insert(User).values({"name": user.name, "surname": user.surname, "hashed_password": user.hashed_password}))
        await database.execute(text("commit;"))
        id = await database.execute(text('select max(id) from users;'))
        user = await database.execute(select(User).where(User.id == id.scalars().one()))
        return user.scalars().one()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Произошла ошибка в добавлении объекта {user}")
# Частичное данных пользователя
@U_R.patch("/{id}", response_model=Union[Secondary_User, New_Respons], tags=[Tags.users])
async def edit_user(id: int, item: Annotated[Main_User, Body(embed=True, description="Изменяем данные по id")],
                    database: AsyncSession = Depends(get_session)):
    try:
        user = await database.execute(select(User).where(User.id == id))
        user = user.scalars().one()
    except Exception as e:
        return JSONResponse(status_code=404, content={"message": "Пользователь не найден"})
    try:
        new_data = item.model_dump(exclude_unset=True)
        await database.execute(update(User).values(new_data).where(User.id == id))
        await database.execute(text("commit;"))
        user = await database.execute(select(User).where(User.id == id))
        user = user.scalars().one()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Произошла ошибка в изменении объекта {user}")
    return user
# Удаление пользователя
@U_R.delete("/{id}", response_class=JSONResponse, tags=[Tags.users])
async def delete_person(id: int, database: AsyncSession = Depends(get_session)):
    user = await database.execute(select(User).where(User.id == id))
    if user.first() == None:
        return JSONResponse(status_code=404, content={"message": "Пользователь не найден"})
    try:
        await database.execute(text(f'delete from users where id={id};'))
        await database.execute(text("commit;"))
    except HTTPException:
        JSONResponse(content={"message": "Ошибка"})
    return JSONResponse(content={"message": f"Пользователь удалён {id}"})