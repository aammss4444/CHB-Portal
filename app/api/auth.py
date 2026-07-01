from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import (
    verify_password, create_access_token, create_refresh_token, get_password_hash, get_current_user,
    create_password_reset_token, verify_password_reset_token, RoleChecker
)
from app.core.config import settings
from app.schemas.user import Token, UserResponse, PasswordResetRequest, PasswordResetConfirm, CandidateRegister, UserUpdate, UserAdminCreate, RefreshTokenRequest
from app.schemas.pagination import PaginatedResponse
from app.dependencies.pagination import PaginationParams, paginate
from app.models.user import User, RoleEnum
from jose import jwt

from sqlalchemy import select, or_
from app.services.notification_service import send_password_reset_email
from app.models.audit import AuditLog

router = APIRouter(prefix="/auth", tags=["Authentication"])
admin_only = RoleChecker([RoleEnum.ADMIN])

@router.post("/login", response_model=Token)
async def login_for_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    result = await db.execute(select(User).filter(
        or_(User.email == form_data.username, User.phone_number == form_data.username)
    ))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(subject=user.id)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }

@router.post("/refresh")
async def refresh_access_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Refresh the access token using a valid refresh token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(request.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        if payload.get("scope") != "refresh":
            raise credentials_exception
    except jwt.JWTError:
        raise credentials_exception
        
    result = await db.execute(select(User).filter(User.id == int(user_id)))
    user = result.scalars().first()
    if user is None or (hasattr(user, "is_active") and not user.is_active):
        raise credentials_exception
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserResponse, dependencies=[Depends(admin_only)])
async def register_user(
    user_in: UserAdminCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin only: Register a new system user.
    """
    result = await db.execute(select(User).filter(User.email == user_in.email))
    user = result.scalars().first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        role=user_in.role,
        full_name=user_in.full_name,
        phone_number=user_in.phone_number,
        institution_id=user_in.institution_id,
    )

    db.add(db_user)
    await db.flush()

    from app.models.audit import AuditLog
    db.add(AuditLog(
        entity_name="User",
        entity_id=str(db_user.id),
        action="REGISTER",
        user_id=current_user.id,
        new_value={"email": db_user.email, "role": db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)}
    ))

    await db.commit()
    return db_user

from app.models.audit import AuditLog
from app.models.candidate import Candidate

@router.post("/candidate/register", response_model=UserResponse)
async def candidate_register(user_in: CandidateRegister, db: Session = Depends(get_db)):
    """
    Public endpoint for candidate registration.
    Sets role to CANDIDATE automatically and creates a Candidate profile.
    """
    result = await db.execute(select(User).filter(User.email == user_in.email))
    user = result.scalars().first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        role=RoleEnum.CANDIDATE,
        full_name=user_in.full_name,
        phone_number=user_in.phone_number,
    )

    db.add(db_user)
    await db.flush()

    # Create Candidate Profile
    db_candidate = Candidate(
        user_id=db_user.id,
        full_name=user_in.full_name,
        email=user_in.email,
        mobile=user_in.phone_number
    )
    db.add(db_candidate)
    await db.flush()

    db.add(AuditLog(
        entity_name="User",
        entity_id=str(db_user.id),
        action="CANDIDATE_REGISTER",
        user_id=db_user.id,
        new_value={"email": db_user.email, "role": RoleEnum.CANDIDATE.value, "candidate_id": str(db_candidate.id)}
    ))

    await db.commit()
    return db_user


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("", response_model=PaginatedResponse[UserResponse])
async def read_users(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """
    Admin only: List all users in the system.
    """
    query = select(User)
    return await paginate(db, query, pagination)


@router.post("/forgot-password")
async def forgot_password(request: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Initiates a password reset flow. Sends an email to the user if the account exists.
    """
    result = await db.execute(select(User).filter(User.email == request.email))
    user = result.scalars().first()
    
    if user and hasattr(user, "is_active") and user.is_active:
        token = create_password_reset_token(user.email)
        await send_password_reset_email(user.email, token)
        
    # Always return success to prevent email enumeration
    return {"message": "If an account exists with this email, a reset link has been sent."}

@router.post("/reset-password")
async def reset_password(request: PasswordResetConfirm, db: Session = Depends(get_db)):
    """
    Resets the password using a valid token.
    """
    email = verify_password_reset_token(request.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
        
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
        
    hashed_password = get_password_hash(request.new_password)
    user.hashed_password = hashed_password
    
    db.add(AuditLog(
        entity_name="User",
        entity_id=str(user.id),
        action="PASSWORD_RESET",
        user_id=user.id,
        new_value={"email": user.email, "status": "password_reset_successful"}
    ))
    
    await db.commit()
    return {"message": "Password has been successfully reset."}

@router.post("/", response_model=UserResponse, dependencies=[Depends(admin_only)])
async def admin_create_user(user_in: UserAdminCreate, db: Session = Depends(get_db)):
    """
    Admin only: Create a new user with full control.
    """
    result = await db.execute(select(User).filter(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        role=user_in.role,
        full_name=user_in.full_name,
        phone_number=user_in.phone_number,
        institution_id=user_in.institution_id
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.get("/{user_id}", response_model=UserResponse, dependencies=[Depends(admin_only)])
async def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    """
    Admin only: Get details of a specific user.
    """
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.patch("/{user_id}", response_model=UserResponse, dependencies=[Depends(admin_only)])
async def update_user(user_id: int, user_in: UserUpdate, db: Session = Depends(get_db)):
    """
    Admin only: Update a user's information.
    """
    result = await db.execute(select(User).filter(User.id == user_id))
    db_user = result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.delete("/{user_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(admin_only)])
async def delete_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Admin only: Delete a user from the system.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
        
    result = await db.execute(select(User).filter(User.id == user_id))
    db_user = result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(db_user)
    await db.commit()
    return {"status": "success", "message": f"User {user_id} has been deleted."}


@router.patch("/users/{user_id}", response_model=UserResponse, dependencies=[Depends(admin_only)])
async def update_user_alias(user_id: int, user_in: UserUpdate, db: Session = Depends(get_db)):
    """Admin alias endpoint for updating a user."""
    return await update_user(user_id=user_id, user_in=user_in, db=db)


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(admin_only)])
async def delete_user_alias(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin alias endpoint for deleting a user."""
    return await delete_user(user_id=user_id, db=db, current_user=current_user)
