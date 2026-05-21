from fastapi import (
    APIRouter,
    HTTPException,
    Depends
)
from fastapi.security import OAuth2PasswordRequestForm
from config import get_db_connection

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
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if user already exists
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )
    
    hashed_password = hash_password(password)

    # Insert user
    cursor.execute(
        "INSERT INTO users (email, password) VALUES (?, ?)", 
        (email, hashed_password)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    return {
        "message": "User created",
        "user_id": str(user_id)
    }

# -------------------------
# LOGIN (SWAGGER COMPATIBLE)
# -------------------------

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    conn = get_db_connection()
    cursor = conn.cursor()

    # form_data.username will contain the provided email
    cursor.execute("SELECT * FROM users WHERE email = ?", (form_data.username,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    # Note: user["password"] works because of conn.row_factory = sqlite3.Row in config
    if not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    token = create_access_token({
        "sub": str(user["id"])
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }
