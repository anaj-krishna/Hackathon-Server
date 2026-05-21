from fastapi import (
    APIRouter,
    HTTPException
)

from config import mongo_db

from auth.security import (
    hash_password,
    verify_password,
    create_access_token
)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

# -------------------------
# REGISTER
# -------------------------

@router.post("/register")
async def register(
    email: str,
    password: str
):

    if mongo_db is None:

        raise HTTPException(
            status_code=500,
            detail="MongoDB is not configured"
        )

    existing_user = await mongo_db.users.find_one({
        "email": email
    })

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    hashed_password = hash_password(
        password
    )

    result = await mongo_db.users.insert_one({
        "email": email,
        "password": hashed_password
    })

    return {
        "message": "User created",
        "user_id": str(result.inserted_id)
    }

# -------------------------
# LOGIN
# -------------------------

@router.post("/login")
async def login(
    email: str,
    password: str
):

    if mongo_db is None:

        raise HTTPException(
            status_code=500,
            detail="MongoDB is not configured"
        )

    user = await mongo_db.users.find_one({
        "email": email
    })

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(
        password,
        user["password"]
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    token = create_access_token({
        "sub": str(user["_id"])
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }